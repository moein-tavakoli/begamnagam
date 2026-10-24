#!/usr/bin/env python3
"""Low-activity1000-account benchmark: isolated PostgreSQL/cache/queue; demo only.

Use backend/.venv/bin/python. Supply BENCH_DATABASE_URL, BENCH_REDIS_URL (DB14),
BENCH_BROKER_URL via the environment, never CLI credentials. No image build.
"""
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse, urlunparse
import urllib.request
import uuid
import psycopg
from psycopg import sql
from redis import Redis

ROOT = Path(__file__).resolve().parent.parent


def percentile(values, p):
    return round(sorted(values)[max(0,math.ceil(len(values)*p)-1)],3) if values else None


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
    runtime_sources = [ROOT/'backend/config/settings.py', ROOT/'backend/config/urls.py', *[ROOT/'backend/core'/name for name in ['models.py','views.py','services.py','tasks.py','safety.py','recipient.py','privacy.py','fields.py','budget.py','provider_services.py','provider_delivery.py','moderation.py','middleware.py']]]
    def source_hash(): return hashlib.sha256(b''.join(p.read_bytes() for p in runtime_sources)).hexdigest()
    runtime_sources += sorted((ROOT/'backend/core/providers').glob('*.py'))
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
        BENCHMARK_RUN_ID=run_id,DEBUG='1',DEMO_MODE='1',DJANGO_TESTING='0',CELERY_TASK_ALWAYS_EAGER='0',
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
    samples=[];lock=threading.Lock();client_locks=[threading.Lock() for _ in range(10)]
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
        clients=[Client() for _ in range(10)]
        flow_latencies=[]
        for i,client in enumerate(clients):
            client.call('/bootstrap')
            client.login('099'+str(i).zfill(8))
        # Thirty complete successful journeys, respecting the3/day sender cap.
        for j in range(3):
            for i,client in enumerate(clients):
                started=time.monotonic()
                recipient='098'+str(j*10+i).zfill(8)
                preview=client.call('/messages/preview',{'category':['appreciation','encouragement','congratulations'][j],'text':'یک پیام مثبت مصنوعی برای آزمون محلی','recipient_phone':recipient})
                key=str(uuid.uuid4())
                order=client.call('/orders',{'preview_id':preview['preview_id'],'recipient_phone':recipient},key=key)
                assert client.call('/orders',{'preview_id':preview['preview_id'],'recipient_phone':recipient},key=key)['id']==order['id']
                client.call('/orders/'+order['id']+'/pay-demo',{})
                for _ in range(50):
                    result=client.call('/orders/'+order['id'])
                    if result['status']=='delivered_demo': break
                    time.sleep(.1)
                else: raise RuntimeError('Successful-flow queue did not complete')
                flow_latencies.append((time.monotonic()-started)*1000)
        print('Prepared1000 accounts/10 active sessions;30 successful demo journeys complete.',flush=True)

        def request_one(index,phase):
            path=['/bootstrap','/messages','/preferences'][index%3]
            client_index=index%10
            with client_locks[client_index]:
                start=time.monotonic();success=True
                try: clients[client_index].call(path)
                except Exception: success=False
                elapsed=(time.monotonic()-start)*1000
            with lock: samples.append({'phase':phase,'operation':path,'ms':elapsed,'success':success})

        def load(phase,duration,rate):
            began=time.monotonic()
            with ThreadPoolExecutor(max_workers=10) as pool:
                futures=[]
                for n in range(duration*rate):
                    remaining=began+n/rate-time.monotonic()
                    if remaining>0: time.sleep(remaining)
                    futures.append(pool.submit(request_one,n,phase))
                for f in futures:f.result()
            print(phase+' complete; measured requests='+str(duration*rate),flush=True)

        load('baseline',args.duration,args.rate)
        load('burst',args.burst_duration,args.burst_rate)
        phase_results={}
        for phase in ['baseline','burst']:
            rows=[r for r in samples if r['phase']==phase]
            timings=[r['ms'] for r in rows if r['success']]
            failures=sum(not r['success'] for r in rows)
            phase_results[phase]={'requests':len(rows),'successful':len(timings),'unexpected_errors':failures,
                'p50_ms':percentile(timings,.5),'p95_ms':percentile(timings,.95),'p99_ms':percentile(timings,.99),
                'error_rate':failures/len(rows) if rows else 0,'operations':{p:sum(r['operation']==p for r in rows) for p in ['/bootstrap','/messages','/preferences']}}
        with psycopg.connect(runtime['DATABASE_URL']) as conn:
            counts=conn.execute("SELECT (SELECT count(*) FROM core_account),(SELECT count(*) FROM core_order WHERE status='delivered_demo'),(SELECT count(*) FROM core_financialevent WHERE kind='payment'),(SELECT count(*) FROM core_messagedelivery WHERE attempts<>1),(SELECT count(*) FROM core_outbox WHERE state<>'sent')").fetchone()
        (folder/'samples.json').write_text(json.dumps(samples))
        from kombu import Connection
        with Connection(broker, connect_timeout=5) as broker_connection:
            broker_connection.connect()
            broker_version=broker_connection.connection.server_properties.get('version','unknown')
        report={'runtime_source_sha256':initial_source_hash,'source_unchanged_during_run':source_hash()==initial_source_hash,'rabbitmq_version':broker_version,'redis_version':redis.info()['redis_version'],'run_id':run_id,'date_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            'database':db,'environment':{'platform':platform.platform(),'logical_cpu_count':os.cpu_count(),'python':platform.python_version(),'http_server':'native gunicorn2 workers x2 threads','queue_worker':'Celery threads concurrency2','dependencies':'local Docker PostgreSQL17/Redis/RabbitMQ; shared development host'},
            'configured':{'baseline_duration_seconds':args.duration,'baseline_rps':args.rate,'burst_duration_seconds':args.burst_duration,'burst_rps':args.burst_rate},
            'seeded_accounts':counts[0],'active_sessions':10,'successful_message_flows':counts[1],'payment_captures':counts[2],
            'delivery_attempt_mismatches':counts[3],'outbox_not_sent':counts[4],'full_demo_flow_p95_ms':percentile(flow_latencies,.95),
            'http':phase_results,'real_provider_capacity_measured':False,'frontend_or_device_performance_measured':False}
        report['passed']=all(v['error_rate']<.01 and (v['p95_ms'] is None or v['p95_ms']<=800) for v in phase_results.values()) and counts==(1000,30,30,0,0) and report['source_unchanged_during_run']
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
