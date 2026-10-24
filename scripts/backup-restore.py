#!/usr/bin/env python3
"""Encrypted local Compose PostgreSQL backups and non-destructive restore rehearsal.

Run with backend/.venv/bin/python. Never restores over a source database, never
resumes dispatch and never prints keys, phones, report text or capability links.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from cryptography.fernet import Fernet, MultiFernet, InvalidToken

ROOT = Path(__file__).resolve().parent.parent
MAGIC = b'BNBACKUP1\n'


def private_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(data)


class Postgres:
    def __init__(self, project):
        if not re.fullmatch(r'begamnagam(?:-[a-z0-9-]+)?', project):
            raise ValueError('Only this project family is allowed')
        self.base = ['docker', 'compose', '-p', project, '-f', str(ROOT/'compose.yaml'), 'exec', '-T', 'postgres', 'sh', '-c']

    def run(self, script, *args, data=None):
        result = subprocess.run([*self.base, script, '--', *args], input=data, capture_output=True, timeout=180, cwd=ROOT)
        if result.returncode:
            raise RuntimeError('PostgreSQL command failed; private diagnostics withheld')
        return result.stdout

    def sql(self, sql, db=None):
        script = 'exec psql -X -v ON_ERROR_STOP=1 -A -t -U "$POSTGRES_USER" -d "$POSTGRES_DB"' if not db else 'exec psql -X -v ON_ERROR_STOP=1 -A -t -U "$POSTGRES_USER" -d "$1"'
        return self.run(script, *([db] if db else []), data=sql.encode()).decode().strip()

    def rows(self, table_query, db=None):
        raw = self.sql('SELECT row_to_json(r) FROM ('+table_query+') r;', db)
        return [json.loads(line) for line in raw.splitlines() if line.strip()]


def quote(value):
    return 'NULL' if value is None else "'" + str(value).replace("'", "''") + "'"


def financial_check(pg, db=None):
    return int(pg.sql("""SELECT count(*) FROM core_financialevent e
        JOIN core_paymentattempt p ON p.id=e.payment_id
        LEFT JOIN core_refund r ON r.id=e.refund_id
        WHERE e.amount_toman<>p.amount_toman OR (e.kind='refund' AND (r.status<>'refunded' OR r.amount_toman<>e.amount_toman));""", db))


def source_watermark(pg, db=None):
    return {row['id'] for row in pg.rows('SELECT id::text AS id FROM core_financialevent', db)}


def privacy_overlay(pg):
    return {'recipients':pg.rows('SELECT phone_hash,blocked,last_sent_at,updated_at FROM core_recipientstate'),
        'deletions':pg.rows('SELECT phone_hash,deletion_requested_at FROM core_account WHERE deletion_requested_at IS NOT NULL'),
        'budgets':pg.rows('SELECT day,reserved_rial,limit_rial FROM core_spendbudget')}


def apply_overlay(pg, db, overlay):
    statements = ['BEGIN;']
    for item in overlay['recipients']:
        assert re.fullmatch('[a-f0-9]{64}', item['phone_hash'])
        statements.append("INSERT INTO core_recipientstate(phone_hash,blocked,last_sent_at,updated_at) VALUES (%s,%s,%s,%s) ON CONFLICT(phone_hash) DO UPDATE SET blocked=excluded.blocked,last_sent_at=excluded.last_sent_at,updated_at=excluded.updated_at WHERE excluded.updated_at>core_recipientstate.updated_at;" % (quote(item['phone_hash']), 'true' if item['blocked'] else 'false', quote(item['last_sent_at']), quote(item['updated_at'])))
    for item in overlay['deletions']:
        statements.append('UPDATE core_account SET deletion_requested_at=%s,suspended=true WHERE phone_hash=%s;' % (quote(item['deletion_requested_at']),quote(item['phone_hash'])))
    for item in overlay['budgets']:
        statements.append('INSERT INTO core_spendbudget(day,reserved_rial,limit_rial) VALUES (%s,%s,%s) ON CONFLICT(day) DO UPDATE SET reserved_rial=GREATEST(core_spendbudget.reserved_rial,excluded.reserved_rial),limit_rial=LEAST(core_spendbudget.limit_rial,excluded.limit_rial);' % (quote(item['day']),int(item['reserved_rial']),int(item['limit_rial'])))
    # Financial receipts may have changed after a snapshot. All non-demo restored
    # submission intents become query-only; a queued row must never blindly resend.
    statements += ["UPDATE core_messagedelivery SET status='unknown',lease_until=NULL WHERE provider<>'demo' AND status IN ('queued','submitting');",
        "UPDATE core_order SET status='unknown' WHERE id IN (SELECT order_id FROM core_messagedelivery WHERE provider<>'demo' AND status='unknown');",
        "UPDATE core_outbox SET state='unknown' WHERE order_id IN (SELECT order_id FROM core_messagedelivery WHERE provider<>'demo' AND status='unknown');",
        "INSERT INTO core_safetycontrol(id,halted,updated_at) VALUES(1,true,NOW()) ON CONFLICT(id) DO UPDATE SET halted=true,updated_at=NOW();",
        "INSERT INTO core_operatoraudit(id,actor_id,action,object_id,reason,before,after,created_at) VALUES (%s,NULL,'restore_halted','global','restore_reconciliation_required','{}','{\"halted\":true}',NOW());" % quote(uuid.uuid4()), 'COMMIT;']
    pg.sql('\n'.join(statements), db)


def validate_ciphertexts(pg, db):
    # The application encryption keys are deliberately not in the archive. They
    # must be recovered separately; this check catches a wrong-key restore.
    env = {}
    if (ROOT/'.env').exists():
        env.update(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if line and not line.startswith('#') and '=' in line)
    env.update(os.environ)
    key = env.get('PHONE_ENCRYPTION_KEY')
    if not key:
        raise RuntimeError('Application encryption key required for restore validation')
    crypto = MultiFernet([Fernet(k.encode()) for k in [key, *filter(None, env.get('PHONE_ENCRYPTION_FALLBACK_KEYS','').split(','))]])
    count = 0
    for table, field in [('core_account','phone_cipher'),('core_otpchallenge','phone_cipher'),('core_order','recipient_cipher'),('core_order','full_sms'),('core_preview','full_sms'),('core_abusereport','details')]:
        for row in pg.rows(f'SELECT {field} AS cipher FROM {table} WHERE {field}<>\'\'', db):
            value = row['cipher']
            if field in {'full_sms','details'}:
                if not value.startswith('enc:v1:'): raise RuntimeError('Unencrypted capability snapshot found')
                value = value[7:]
            crypto.decrypt(value.encode())
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init-key','backup','restore'])
    parser.add_argument('--project', default='begamnagam')
    parser.add_argument('--key-file', required=True)
    parser.add_argument('--archive')
    parser.add_argument('--target-db')
    parser.add_argument('--report')
    args = parser.parse_args()
    if args.action == 'init-key':
        private_write(args.key_file, Fernet.generate_key()+b'\n')
        print('Private backup key created. Store a separate offline copy; do not commit it.')
        return
    key = Path(args.key_file)
    if key.stat().st_mode & 0o077:
        raise RuntimeError('Backup key permissions must be0600')
    crypto = Fernet(key.read_bytes().strip())
    pg = Postgres(args.project)
    if not args.archive:
        raise ValueError('--archive is required')
    started = time.monotonic()
    if args.action == 'backup':
        dump = pg.run('exec pg_dump -U "$POSTGRES_USER" --format=custom "$POSTGRES_DB"')
        if len(dump) > 256*1024*1024:
            raise ValueError('Archive exceeds initial-product memory limit; use a streaming backup system')
        meta = {'created_utc':datetime.now(timezone.utc).isoformat(), 'sha256':hashlib.sha256(dump).hexdigest(),
            'git_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'schema':pg.rows("SELECT name FROM django_migrations WHERE app='core' ORDER BY applied"),
            'privacy':privacy_overlay(pg)}
        private_write(args.archive,MAGIC+crypto.encrypt(json.dumps(meta).encode()+b'\n'+dump))
        report = {'action':'backup','encrypted':True,'dump_bytes':len(dump),'duration_seconds':round(time.monotonic()-started,3),'schema_tip':meta['schema'][-1]['name']}
    else:
        target = args.target_db or 'begamnagam_restore_'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        if not re.fullmatch(r'begamnagam_restore_[a-z0-9_]{1,40}',target):
            raise ValueError('Restore only allowed into a new begamnagam_restore_* database')
        blob = Path(args.archive).read_bytes()
        if not blob.startswith(MAGIC): raise ValueError('Unknown archive format')
        plain = crypto.decrypt(blob[len(MAGIC):])
        header,dump = plain.split(b'\n',1)
        meta=json.loads(header)
        if hashlib.sha256(dump).hexdigest()!=meta['sha256']: raise ValueError('Archive checksum mismatch')
        if pg.sql('SELECT count(*) FROM pg_database WHERE datname='+quote(target)+';') != '0':
            raise ValueError('Restore target exists; it will not be overwritten')
        latest = privacy_overlay(pg)
        before = source_watermark(pg)
        pg.run('exec createdb -U "$POSTGRES_USER" "$1"',target)
        pg.run('exec pg_restore -U "$POSTGRES_USER" --dbname="$1" --no-owner --no-acl --single-transaction',target,data=dump)
        apply_overlay(pg,target,latest)
        restored_states = {r['phone_hash']: r['blocked'] for r in pg.rows('SELECT phone_hash,blocked FROM core_recipientstate',target)}
        privacy_mismatches = sum(restored_states.get(r['phone_hash']) != r['blocked'] for r in latest['recipients'])
        drift = len(before - source_watermark(pg,target))
        invariant_failures = financial_check(pg,target)
        ciphers = validate_ciphertexts(pg,target)
        report = {'action':'restore','target_database':target,'overwrote_existing_database':False,
            'dispatch_halted':pg.sql('SELECT halted FROM core_safetycontrol WHERE id=1;',target)=='t',
            'financial_invariant_failures':invariant_failures,'post_snapshot_financial_events_missing':drift,
            'suppression_overlay_mismatches':privacy_mismatches,'recipient_states_overlaid':len(latest['recipients']),'deletion_requests_overlaid':len(latest['deletions']),
            'encrypted_fields_validated':ciphers,'duration_seconds':round(time.monotonic()-started,3),
            'archive_age_seconds':round((datetime.now(timezone.utc)-datetime.fromisoformat(meta['created_utc'])).total_seconds(),3),
            'rehearsal_pass':not drift and not invariant_failures and not privacy_mismatches,'production_resume_authorized':False}
    if args.report:
        private_write(args.report,(json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(report,indent=2))
    if args.action=='restore' and not report['rehearsal_pass']: raise SystemExit(2)


if __name__=='__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, InvalidToken, subprocess.SubprocessError) as exc:
        # Crypto/SQL errors are intentionally not printed with private payloads.
        print('Backup/restore stopped safely: '+type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
