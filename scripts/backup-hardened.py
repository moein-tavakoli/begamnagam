#!/usr/bin/env python3
"""Root-only encrypted PostgreSQL backup and optional isolated restore check.

The independent key must be0600 and backed up separately. No providers are
called, no production rows are changed, and private subprocess errors are hidden.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

PG = "begamnagam-internal-postgres-1"
BACKEND = "begamnagam-internal-backend-1"


def run(command, data=None):
    result = subprocess.run(command, input=data, capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError("Private backup subprocess failed")
    return result.stdout


def private_write(path, body):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as target:
        target.write(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--check-restore", action="store_true")
    args = parser.parse_args()
    key = Path(args.key_file)
    if key.stat().st_mode & 0o077:
        raise ValueError("Backup key requires0600")
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    config = json.loads(run(["docker", "inspect", PG]))[0]["Config"]["Env"]
    values = dict(item.split("=", 1) for item in config if "=" in item)
    admin, database = values["POSTGRES_USER"], values["POSTGRES_DB"]
    base = ["docker", "exec", "-i", "-u", "postgres", PG]
    dump = run([*base, "pg_dump", "-U", admin, "--format=custom", database])
    if len(dump) > 256 * 1024 * 1024:
        raise ValueError("Use streaming backups beyond the initial-product limit")
    digest = hashlib.sha256(dump).hexdigest()
    crypt = "import sys;from cryptography.fernet import Fernet;k,b=sys.stdin.buffer.read().split(b'\\n',1);sys.stdout.buffer.write(Fernet(k).encrypt(b))"
    encrypted = run(["docker", "exec", "-i", BACKEND, "python", "-c", crypt], key.read_bytes().strip()+b"\n"+dump)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:6]
    archive = folder/("database-"+stamp+".dump.fernet")
    private_write(archive, encrypted)
    result = {"encrypted": True, "archive": str(archive), "dump_bytes": len(dump),
              "plaintext_sha256": digest, "production_rows_changed": False, "real_sms_sent": False}
    if args.check_restore:
        decrypt = crypt.replace(".encrypt(b)", ".decrypt(b)")
        restored_dump = run(["docker", "exec", "-i", BACKEND, "python", "-c", decrypt], key.read_bytes().strip()+b"\n"+encrypted)
        assert hashlib.sha256(restored_dump).hexdigest() == digest
        target = "begamnagam_restore_"+uuid.uuid4().hex[:16]
        run([*base, "createdb", "-U", admin, target])
        try:
            run([*base, "pg_restore", "-U", admin, "--dbname="+target, "--no-owner", "--no-acl", "--single-transaction"], restored_dump)
            sqlbase = [*base, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-At", "-U", admin, "-d", target]
            run(sqlbase, b"UPDATE core_safetycontrol SET halted=true WHERE id=1")
            failures = run(sqlbase, b"SELECT count(*) FROM core_financialevent e JOIN core_paymentattempt p ON p.id=e.payment_id LEFT JOIN core_refund r ON r.id=e.refund_id WHERE e.amount_toman<>p.amount_toman OR (e.kind='refund' AND (r.status<>'refunded' OR r.amount_toman<>e.amount_toman))")
            assert failures.strip() == b"0"
            fields = [('core_account','phone_cipher'),('core_otpchallenge','phone_cipher'),('core_order','recipient_cipher'),('core_order','full_sms'),('core_preview','full_sms'),('core_preview','generated_body'),('core_preview','original_text'),('core_abusereport','details'),('core_invitation','phone_cipher'),('core_invitationsend','full_sms'),('core_order','text'),('core_preview','text')]
            # Pre-migration backups must still rehearse against their original schema.
            optional_tables = set(json.loads(run(sqlbase, b"SELECT coalesce(json_agg(tablename),'[]'::json) FROM pg_tables WHERE schemaname='public' AND tablename IN ('core_manualpaymentsettings','core_manualpayment','core_supportmessage','core_botconversation')")))
            fields.extend((table, field) for table, field in [
                ('core_manualpaymentsettings', 'card_number'), ('core_manualpayment', 'card_number'),
                ('core_manualpayment', 'receipt_reference'), ('core_manualpayment', 'confirmed_reference'), ('core_supportmessage', 'text'),
                ('core_botconversation', 'user_id'), ('core_botconversation', 'chat_id'),
                ('core_botconversation', 'session_key'), ('core_botconversation', 'data')]
                if table in optional_tables)
            selects = ["SELECT json_build_array('"+field+"',"+field+") FROM "+table+" WHERE "+field+"<>''" for table,field in fields]
            rows = run(sqlbase, (";\n".join(selects)+";").encode())
            # Only the backend has the application keys. Never grant its runtime
            # role access to the rehearsal DB, or attach a worker to that DB.
            check = """import django,json,sys;django.setup()
from core.privacy import decrypt
from core.models import Order
from core.fields import EncryptedTextField
total=0
for line in sys.stdin:
 field,value=json.loads(line)
 if field=='text' and not value.startswith('enc:v1:'):
  assert not isinstance(Order._meta.get_field('text'),EncryptedTextField)
  continue
 decrypt(value[7:] if value.startswith('enc:v1:') else value);total+=1
print(json.dumps({'restore_check':'PASS','encrypted_fields_validated':total,'dispatch_on_restored_database':'halted'}))
"""
            result.update(json.loads(run(["docker", "exec", "-i", BACKEND, "python", "-c", check], rows)))
        finally:
            run([*base, "dropdb", "-U", admin, target])
    private_write(folder/("report-"+stamp+".json"), (json.dumps(result,indent=2)+"\n").encode())
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Backup stopped safely: "+type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
