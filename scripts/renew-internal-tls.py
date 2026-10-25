#!/usr/bin/env python3
"""Renew Traefik's private-IP certificate using the existing private root CA."""
import argparse
import datetime
import ipaddress
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-docker", action="store_true", help="Run the signer in the project's locked backend image")
    parser.add_argument("--force", action="store_true", help="Replace an otherwise valid leaf after a certificate policy change")
    parser.add_argument("--host")
    parser.add_argument("--ca-dir", type=Path, default=Path("/ca/caddy/pki/authorities/local"))
    parser.add_argument("--cert-dir", type=Path, default=Path("/tls"))
    parser.add_argument("--notify-config", type=Path)
    args = parser.parse_args()
    if args.in_docker:
        root = Path(__file__).resolve().parent.parent
        values = dict(line.split("=", 1) for line in (root / ".env.internal").read_text().splitlines()
            if line and not line.startswith("#") and "=" in line)
        cert_dir = Path(values["INTERNAL_TLS_DIR"])
        assert cert_dir.is_absolute()
        cert_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        # This LXC forbids nested network namespaces. The signer opens no sockets.
        command = ["docker", "run", "--rm", "--network", "host", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true",
            "--user", "0:0", "--memory", "128m", "--entrypoint", "python",
            "-v", "begamnagam-internal_caddy-data:/ca:ro",
            "-v", str(cert_dir) + ":/tls",
            "-v", str(root / "deploy/traefik") + ":/config",
            "-v", str(Path(__file__).resolve()) + ":/renew.py:ro", values["BACKEND_IMAGE"],
            "/renew.py", "--host", values["INTERNAL_DEMO_HOST"], "--notify-config", "/config/routes.yml"]
        if args.force:
            command.append("--force")
        subprocess.run(command, check=True)
        return
    address = ipaddress.ip_address(args.host)
    assert any(address in ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    now = datetime.datetime.now(datetime.timezone.utc)
    root = x509.load_pem_x509_certificate((args.ca_dir / "root.crt").read_bytes())
    root_key = serialization.load_pem_private_key((args.ca_dir / "root.key").read_bytes(), password=None)
    assert root.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) == root_key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    assert root.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    assert root.not_valid_before_utc <= now and root.not_valid_after_utc > now + datetime.timedelta(days=31)
    target = args.cert_dir / "tls.crt"
    key_path = args.cert_dir / "tls.key"
    if target.exists() and key_path.exists() and not args.force:
        old = x509.load_pem_x509_certificate(target.read_bytes())
        if old.not_valid_after_utc > now + datetime.timedelta(days=14):
            old.verify_directly_issued_by(root)
            old_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
            assert old.not_valid_before_utc <= now
            assert old.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) == old_key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
            assert address in old.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress)
            print("Internal TLS certificate is valid; renewal is not due.")
            return
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, str(address))]))
        .issuer_name(root.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(address)]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
            encipher_only=None, decipher_only=None), critical=True).sign(root_key, hashes.SHA256()))
    args.cert_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.umask(0o077)
    for path, content, mode in [
        (key_path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()), 0o600),
        (target, cert.public_bytes(serialization.Encoding.PEM), 0o644),
    ]:
        temporary = path.with_suffix(path.suffix + ".new")
        temporary.write_bytes(content)
        temporary.chmod(mode)
        temporary.replace(path)
    if args.notify_config:
        # File-provider watches the parent directory; trigger a config reload.
        args.notify_config.write_bytes(args.notify_config.read_bytes())
    print("Renewed private-IP TLS certificate for 30 days; existing root trust is preserved.")


if __name__ == "__main__":
    main()
