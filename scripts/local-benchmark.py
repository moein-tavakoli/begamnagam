#!/usr/bin/env python3
"""Low-activity 1000-account benchmark: isolated PostgreSQL/cache/queue; demo only.

Use backend/.venv/bin/python. Supply BENCH_DATABASE_URL, BENCH_REDIS_URL (DB14),
BENCH_BROKER_URL via the environment, never CLI credentials. No image build.
Exercises 30 gift sends, then reports scheduled read arrivals by phase and route.
"""
import argparse
import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import secrets
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse, urlunparse
import urllib.request
import uuid
import psycopg
from psycopg import sql
from redis import Redis

ROOT = Path(__file__).resolve().parent.parent
OPERATIONS = ('/bootstrap', '/messages', '/preferences')
ACTIVE_SESSIONS = 10
GIFTS_PER_SESSION = 3


def percentile(values, p):
    return round(sorted(values)[max(0,math.ceil(len(values)*p)-1)],3) if values else None


def summarize(rows):
    timings = [row['ms'] for row in rows if row['outcome'] == 'success']
    failures = sum(row['outcome'] == 'error' for row in rows)
    dropped = sum(row['outcome'] == 'dropped' for row in rows)
    completed = len(timings) + failures
    return {
        'requests': completed,
        'offered': len(rows),
        'completed': completed,
        'dropped': dropped,
        'successful': len(timings),
        'unexpected_errors': failures,
        'p50_ms': percentile(timings, .5),
        'p95_ms': percentile(timings, .95),
        'p99_ms': percentile(timings, .99),
        'error_rate': failures / completed if completed else 0,
        'dropped_rate': dropped / len(rows) if rows else 0,
    }


def measure_request(client, path, phase, due):
    try:
        client.call(path)
    except Exception:
        outcome = 'error'
    else:
        outcome = 'success'
    return {'phase': phase, 'operation': path, 'ms': (time.monotonic() - due) * 1000, 'outcome': outcome}


def load(clients, phase, duration, rate):
    interval = 1 / rate
    rows = []
    futures = []
    pending = {}
    with ThreadPoolExecutor(max_workers=len(clients)) as pool:
        began = time.monotonic()
        for index in range(duration * rate):
            due = began + index * interval
            remaining = due - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            path = OPERATIONS[index % len(OPERATIONS)]
            client_index = index % len(clients)
            previous = pending.get(client_index)
            # A late arrival or busy session counts as dropped instead of joining a client-side backlog.
            if time.monotonic() >= due + interval or (previous is not None and not previous.done()):
                rows.append({'phase': phase, 'operation': path, 'ms': None, 'outcome': 'dropped'})
                continue
            future = pool.submit(measure_request, clients[client_index], path, phase, due)
            pending[client_index] = future
            futures.append(future)
        rows.extend(future.result() for future in futures)
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration',type=int,default=900)
    parser.add_argument('--rate',type=int,default=2)
    parser.add_argument('--burst-duration',type=int,default=60)
    parser.add_argument('--burst-rate',type=int,default=10)
    parser.add_argument('--port',type=int,default=8011)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if not 1 <= args.duration <= 1800 or not 1 <= args.rate <= 10 or not 0 <= args.burst_duration <= 120 or not 1 <= args.burst_rate <= 10:
        raise ValueError('Workload exceeds the local test ceiling')
    dsn,redis_url,broker=[os.environ[key] for key in ['BENCH_DATABASE_URL','BENCH_REDIS_URL','BENCH_BROKER_URL']]
    if any(urlparse(v).hostname not in {'localhost','127.0.0.1','::1'} for v in [dsn,redis_url,broker]) or urlparse(redis_url).path != '/14':
        raise ValueError('Benchmark only permits loopback dependencies and isolated RedisDB14')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',args.port))
    def source_hash():
        runtime_sources = sorted(
            path for directory in ('config', 'core')
            for path in (ROOT / 'backend' / directory).rglob('*.py')
        )
        return hashlib.sha256(b''.join(path.read_bytes() for path in runtime_sources)).hexdigest()
    initial_source_hash=source_hash()
    run_id=uuid.uuid4().hex[:12]
    db='begamnagam_bench_'+run_id
    redis=Redis.from_url(redis_url)
    if redis.dbsize(): raise ValueError('RedisDB14 is not empty; refusing to interfere')
    with psycopg.connect(dsn,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db)))
    parsed=urlparse(dsn)
    runtime=dict(os.environ,DATABASE_URL=urlunparse(parsed._replace(path='/'+db)),REDIS_URL=redis_url,
        CELERY_BROKER_URL=broker,CELERY_TASK_DEFAULT_QUEUE='bench_'+run_id,CACHE_KEY_PREFIX='bench:'+run_id,
        DJANGO_SETTINGS_MODULE='config.settings',PROVIDER_DAILY_BUDGET_UNLIMITED='0',
        BENCHMARK_RUN_ID=run_id,DEBUG='0',DEMO_MODE='1',DJANGO_TESTING='0',CELERY_TASK_ALWAYS_EAGER='0',
        DJANGO_SECRET_KEY=secrets.token_urlsafe(48),PHONE_HASH_KEY=secrets.token_urlsafe(48),
        PHONE_ENCRYPTION_KEY=base64.urlsafe_b64encode(os.urandom(32)).decode(),
        SMS_BACKEND='console',OTP_BACKEND='demo',PAYMENT_BACKEND='demo',AI_MODE='template',
        PROVIDER_NETWORK_MODE='disabled',LIVE_PROVIDERS_ENABLED='0',LOCAL_REAL_OTP_ENABLED='0',PILOT_POSITIVE_ONLY='0',SENDING_WINDOW_ENABLED='0',
        APP_BASE_URL='http://127.0.0.1:'+str(args.port),CSRF_TRUSTED_ORIGINS='http://127.0.0.1:'+str(args.port),
        ALLOWED_HOSTS='127.0.0.1,localhost')
    python=sys.executable
    folder=ROOT/'.local'/('benchmark-'+run_id)
    folder.mkdir(parents=True)
    setup_log=(folder/'setup.log').open('w')
    subprocess.run([python,'manage.py','migrate','--noinput'],cwd=ROOT/'backend',env=runtime,stdout=setup_log,stderr=subprocess.STDOUT,check=True)
    subprocess.run([python,'manage.py','seed_benchmark'],cwd=ROOT/'backend',env=runtime,stdout=setup_log,stderr=subprocess.STDOUT,check=True)
    setup_log.close()
    server_log=(folder/'server.log').open('w');worker_log=(folder/'worker.log').open('w')
    children=[]
    try:
        children.append(subprocess.Popen([python,'-m','gunicorn','config.wsgi:application','--bind','127.0.0.1:'+str(args.port),'--workers','2','--threads','2','--timeout','30','--access-logfile','-','--access-logformat','%(m)s %(U)s %(s)s %(L)s'],cwd=ROOT/'backend',env=runtime,stdout=server_log,stderr=subprocess.STDOUT))
        children.append(subprocess.Popen([python,'-m','celery','-A','config','worker','--hostname=bench_'+run_id+'@%h','--pool=threads','--concurrency=2','--loglevel=WARNING'],cwd=ROOT/'backend',env=runtime,stdout=worker_log,stderr=subprocess.STDOUT))
        base=runtime['APP_BASE_URL']
        for _ in range(60):
            if any(c.poll() is not None for c in children): raise RuntimeError('A benchmark process exited')
            try:
                with urllib.request.urlopen(base+'/healthz',timeout=2) as r:
                    health=json.load(r)
                if health.get('benchmark_run_id')==run_id: break
            except (OSError,ValueError): pass
            time.sleep(.5)
        else: raise RuntimeError('Isolated benchmark server was not ready')
        os.environ['SMOKE_BASE_URL']=base
        sys.path.insert(0,str(ROOT/'scripts'))
        from smoke import Client
        clients=[Client() for _ in range(ACTIVE_SESSIONS)]
        flow_latencies=[]
        for i,client in enumerate(clients):
            bootstrap = client.call('/bootstrap')
            if not bootstrap['demo_mode'] or bootstrap.get('otp_is_real'):
                raise RuntimeError('Benchmark requires demo-only SMS and OTP')
            client.login('099'+str(i).zfill(8))
        for j in range(GIFTS_PER_SESSION):
            for i,client in enumerate(clients):
                started=time.monotonic()
                recipient='098'+str(j*10+i).zfill(8)
                preview=client.call('/messages/preview',{'category':['appreciation','encouragement','congratulations'][j],'text':'یک پیام مثبت مصنوعی برای آزمون محلی','recipient_phone':recipient})
                key=str(uuid.uuid4())
                order=client.call('/orders',{'preview_id':preview['preview_id'],'recipient_phone':recipient},key=key)
                assert client.call('/orders',{'preview_id':preview['preview_id'],'recipient_phone':recipient},key=key)['id']==order['id']
                assert order['is_free'] and order['amount_toman'] == 0
                client.call(f"/orders/{order['id']}/confirm-free", {})
                client.call(f"/orders/{order['id']}/confirm-free", {})
                for _ in range(50):
                    result=client.call('/orders/'+order['id'])
                    if result['status']=='delivered_demo': break
                    time.sleep(.1)
                else: raise RuntimeError('Successful-flow queue did not complete')
                flow_latencies.append((time.monotonic()-started)*1000)
        exhausted_gift_balances = sum(client.call('/bootstrap')['free_sends_remaining'] == 0 for client in clients)
        gift_count = ACTIVE_SESSIONS * GIFTS_PER_SESSION
        print(f'Prepared 1000 accounts, {ACTIVE_SESSIONS} active sessions and {gift_count} demo gift sends.', flush=True)

        samples = []
        phase_results = {}
        for phase, duration, rate in (
            ('baseline', args.duration, args.rate),
            ('burst', args.burst_duration, args.burst_rate),
        ):
            rows = load(clients, phase, duration, rate)
            samples.extend(rows)
            result = summarize(rows)
            by_operation = {
                path: summarize([row for row in rows if row['operation'] == path])
                for path in OPERATIONS
            }
            phase_results[phase] = {
                **result,
                'operations': {path: operation['completed'] for path, operation in by_operation.items()},
                'by_operation': by_operation,
            }
            print(f"{phase} complete: {result['completed']}/{result['offered']} completed.", flush=True)
        with psycopg.connect(runtime['DATABASE_URL']) as conn:
            database_version = conn.execute('SHOW server_version').fetchone()[0]
            counts = conn.execute("""
                SELECT (SELECT count(*) FROM core_account),
                    (SELECT count(*) FROM core_order WHERE status = 'delivered_demo' AND is_free AND amount_toman = 0),
                    (SELECT count(*) FROM core_financialevent WHERE kind = 'payment'),
                    (SELECT count(*) FROM core_messagedelivery WHERE attempts <> 1 OR status <> 'delivered_demo'),
                    (SELECT count(*) FROM core_outbox WHERE state <> 'sent'),
                    (SELECT count(*) FROM core_order),
                    (SELECT count(*) FROM core_messagedelivery),
                    (SELECT count(*) FROM core_outbox)
            """).fetchone()
        (folder/'samples.json').write_text(json.dumps(samples))
        from kombu import Connection
        with Connection(broker, connect_timeout=5) as broker_connection:
            broker_connection.connect()
            broker_version=broker_connection.connection.server_properties.get('version','unknown')
        account_count, gift_deliveries, payment_captures, delivery_mismatches, unsent_outbox, orders, deliveries, outbox_events = counts
        report = {
            'runtime_source_sha256': initial_source_hash,
            'source_unchanged_during_run': source_hash() == initial_source_hash,
            'postgresql_version': database_version,
            'rabbitmq_version': broker_version,
            'redis_version': redis.info()['redis_version'],
            'run_id': run_id,
            'date_utc': datetime.now(timezone.utc).isoformat(),
            'database': db,
            'environment': {
                'platform': platform.platform(),
                'logical_cpu_count': os.cpu_count(),
                'python': platform.python_version(),
                'http_server': 'native Gunicorn, 2 workers × 2 threads',
                'queue_worker': 'Celery threads, concurrency 2',
                'dependencies': 'loopback PostgreSQL/Redis/RabbitMQ',
            },
            'configured': {
                'baseline_duration_seconds': args.duration, 'baseline_rps': args.rate,
                'burst_duration_seconds': args.burst_duration, 'burst_rps': args.burst_rate,
            },
            'seeded_accounts': account_count,
            'active_sessions': len(clients),
            'exhausted_gift_balances': exhausted_gift_balances,
            'successful_message_flows': gift_deliveries,
            'payment_captures': payment_captures,
            'orders': orders,
            'deliveries': deliveries,
            'outbox_events': outbox_events,
            'delivery_attempt_mismatches': delivery_mismatches,
            'outbox_not_sent': unsent_outbox,
            'full_demo_flow_p95_ms': percentile(flow_latencies, .95),
            'http': phase_results,
            'real_provider_capacity_measured': False,
            'frontend_or_device_performance_measured': False,
        }
        report['passed'] = (
            report['source_unchanged_during_run']
            and exhausted_gift_balances == ACTIVE_SESSIONS
            and counts == (1000, gift_count, 0, 0, 0, gift_count, gift_count, gift_count)
            and all(
                result['error_rate'] < .01 and result['dropped'] == 0
                and all(stats['p95_ms'] is None or stats['p95_ms'] <= 800 for stats in result['by_operation'].values())
                for result in phase_results.values()
            )
        )
        output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
        if not report['passed']: raise SystemExit(2)
    finally:
        for child in children:child.terminate()
        for child in children:
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        server_log.close();worker_log.close()
        own_keys=list(redis.scan_iter(match='bench:'+run_id+':*'))
        if own_keys: redis.delete(*own_keys)
        # Own synthetic DB/queue remain for inspection; source demo DB untouched.


if __name__=='__main__':
    main()
