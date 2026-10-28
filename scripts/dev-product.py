#!/usr/bin/env python3
"""Run the authorized real product locally; never load or replay demo orders."""
import os
import argparse
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "backend/.venv/bin/python"
if Path(sys.prefix) != PYTHON.parent.parent:
    os.execv(str(PYTHON), [str(PYTHON), __file__, *sys.argv[1:]])

import psycopg
from psycopg import sql

STATE = ROOT / ".local/local-product"
STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chmod(STATE, 0o700)


def private_environment():
    values = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relax-business-limits", action="store_true", help="Explicitly remove count/time restrictions, preserving three gift credits")
    parser.add_argument("--manage", nargs=argparse.REMAINDER, help="Run a Django management command with the private local product environment")
    options = parser.parse_args()
    for port in (() if options.manage else (3000, 8000)):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(f"Port {port} is occupied; stop the existing local app first.")
    source = private_environment()
    required = ("DJANGO_SECRET_KEY", "PHONE_HASH_KEY", "PHONE_ENCRYPTION_KEY",
                "KAVENEGAR_API_KEY", "KAVENEGAR_SENDER", "POSTGRES_USER",
                "POSTGRES_PASSWORD", "POSTGRES_DB", "RABBITMQ_USER", "RABBITMQ_PASSWORD")
    if any(not source.get(key) for key in required):
        raise SystemExit("Missing private .env credentials; no demo fallback is permitted.")
    database = "begamnagam_local_product"
    with psycopg.connect(host="127.0.0.1", port=15439, user=source["POSTGRES_USER"],
                         password=source["POSTGRES_PASSWORD"], dbname=source["POSTGRES_DB"],
                         autocommit=True) as connection:
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,)).fetchone():
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    env = os.environ.copy()
    for key in required[:5]:
        env[key] = source[key]
    env.update({
        "DJANGO_SETTINGS_MODULE": "config.local_live_settings", "LOCAL_LIVE_PRODUCT_ENABLED": "1",
        "DEBUG": "0", "DEMO_MODE": "0", "DJANGO_TESTING": "0",
        "OTP_BACKEND": "kavenegar", "SMS_BACKEND": "kavenegar", "PAYMENT_BACKEND": "disabled",
        "KAVENEGAR_OTP_MODE": "sms", "KAVENEGAR_BASE_URL": "https://api.kavenegar.com",
        "PROVIDER_NETWORK_MODE": "external", "LIVE_PROVIDERS_ENABLED": "1", "PROVIDER_ENVIRONMENT": "live",
        "LOCAL_REAL_OTP_ENABLED": "0", "DEMO_TEST_TOOLS_ENABLED": "0", "SMS_RECIPIENT_POLICY": "all",
        "PROVIDER_DAILY_BUDGET_UNLIMITED": "1", "PROVIDER_DAILY_BUDGET_RIAL": "100000",
        "SMS_MAX_COST_RIAL": "20000", "OTP_MAX_COST_RIAL": "10000", "PILOT_POSITIVE_ONLY": "0",
        "TERMS_VERSION": "v0.10.2", "APP_BASE_URL": "https://localhost:3000",
        "ALLOWED_HOSTS": "localhost,127.0.0.1", "CSRF_TRUSTED_ORIGINS": "https://localhost:3000",
        "TRUST_DOMAIN_PROXY": "0", "TRUST_INTERNAL_PROXY": "0", "PUBLIC_DEMO_HOST": "", "INTERNAL_DEMO_HOST": "",
        "DATABASE_URL": f"postgresql://{quote(source['POSTGRES_USER'], safe='')}:{quote(source['POSTGRES_PASSWORD'], safe='')}@127.0.0.1:15439/{database}",
        "REDIS_URL": "redis://127.0.0.1:16389/8", "CACHE_KEY_PREFIX": "begamnagam-local-real-v1",
        "CELERY_BROKER_URL": f"amqp://{quote(source['RABBITMQ_USER'], safe='')}:{quote(source['RABBITMQ_PASSWORD'], safe='')}@127.0.0.1:15679//",
        "CELERY_TASK_ALWAYS_EAGER": "0", "CELERY_TASK_DEFAULT_QUEUE": "begamnagam-local-real",
        "AI_MODE": source.get("AI_MODE", "template"),
        "GAPGPT_API_KEY": source.get("GAPGPT_API_KEY", ""),
        "GAPGPT_MODEL": source.get("GAPGPT_MODEL", "gpt-4.1-mini"),
        "GAPGPT_BASE_URL": source.get("GAPGPT_BASE_URL", "https://api.gapgpt.app/v1"),
        "GAPGPT_TIMEOUT_SECONDS": source.get("GAPGPT_TIMEOUT_SECONDS", "5"),
        "GAPGPT_DAILY_REQUEST_LIMIT": source.get("GAPGPT_DAILY_REQUEST_LIMIT", "0"),
        "GAPGPT_DAILY_REQUEST_UNLIMITED": source.get("GAPGPT_DAILY_REQUEST_UNLIMITED", "0"),
        "GAPGPT_USER_DAILY_LIMIT": source.get("GAPGPT_USER_DAILY_LIMIT", "0"),
    })
    if Path("/etc/ssl/cert.pem").exists():
        env["SSL_CERT_FILE"] = "/etc/ssl/cert.pem"
    subprocess.run([str(PYTHON), "manage.py", "migrate", "--noinput"], cwd=ROOT / "backend", env=env, check=True)
    if options.manage:
        return subprocess.run([str(PYTHON), "manage.py", *options.manage], cwd=ROOT / "backend", env=env, check=True)
    os.environ.update(env)
    sys.path.insert(0, str(ROOT / "backend"))
    import django
    django.setup()
    from core.models import MessageDelivery, OperatorAudit, Order, PaymentAttempt, SafetyControl
    if ((Order.objects.exists() and not OperatorAudit.objects.filter(action="local_product_launch").exists())
            or MessageDelivery.objects.filter(environment="demo").exists()
            or PaymentAttempt.objects.filter(environment="demo").exists()):
        raise SystemExit("Refusing to run real workers against existing demo/unidentified orders.")
    control, created = SafetyControl.objects.get_or_create(pk=1, defaults={"halted": False})
    if created:
        OperatorAudit.objects.create(action="local_product_launch", object_id="local",
            reason="User requested local real product testing", after={"halted": False})
    if control.halted:
        raise SystemExit("Local sending was paused; inspect the existing safety control before resuming.")
    command = [str(PYTHON), "manage.py", "configure_limits", "--reason",
               "User requested local removal of count/time restrictions; preserve three gifts" if options.relax_business_limits else "Initialize admin-visible local product policy"]
    if options.relax_business_limits:
        command.append("--relax-business")
    subprocess.run(command, cwd=ROOT / "backend", env=env, check=True)
    subprocess.run([str(PYTHON), "manage.py", "collectstatic", "--noinput", "--verbosity", "0"], cwd=ROOT / "backend", env=env, check=True)
    certificate, key = STATE / "localhost.crt", STATE / "localhost.key"
    if not certificate.exists() or not key.exists():
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "14",
                        "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
                        "-keyout", str(key), "-out", str(certificate)], check=True, capture_output=True)
        os.chmod(key, 0o600)
    # Never pass provider/database/phone keys into the frontend development process.
    ui_env = {key: value for key, value in os.environ.items() if key in
              {"PATH", "HOME", "TMPDIR", "USER", "SHELL", "LANG", "LC_ALL", "TERM"}}
    ui_env.update({"INTERNAL_API_URL": "https://127.0.0.1:8000", "APP_BASE_URL": "https://localhost:3000",
                   "NODE_EXTRA_CA_CERTS": str(certificate), "SEO_INDEXABLE": "0", "BUILD_STANDALONE": "0"})
    commands = [
        ("backend", [str(PYTHON), str(ROOT / "scripts/local-product-api.py")], ROOT / "backend", env),
        ("worker", [str(PYTHON), "-m", "celery", "-A", "config", "worker", "--pool=solo", "--loglevel=WARNING", "--queues=begamnagam-local-real"], ROOT / "backend", env),
        ("beat", [str(PYTHON), "-m", "celery", "-A", "config", "beat", "--loglevel=WARNING", "--schedule", str(STATE / "celerybeat-schedule")], ROOT / "backend", env),
        ("frontend", [shutil.which("npm"), "run", "dev", "--", "--experimental-https", "--experimental-https-key", str(key), "--experimental-https-cert", str(certificate), "--experimental-https-ca", str(certificate)], ROOT / "frontend", ui_env),
    ]
    processes, logs = [], []
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        for name, command, directory, process_env in commands:
            log_path = STATE / f"{name}.log"
            log = open(log_path, "a")
            os.chmod(log_path, 0o600)
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=directory, env=process_env, stdout=log, stderr=log, start_new_session=True))
        print("Local real product: https://localhost:3000 (OTP/SMS real; paid checkout disabled)", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(1)
        raise RuntimeError("A local service stopped; inspect .local/local-product/*.log")
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for log in logs:
            log.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
