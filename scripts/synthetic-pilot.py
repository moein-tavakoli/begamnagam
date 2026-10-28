#!/usr/bin/env python3
"""Create a new loopback-only PostgreSQL pilot DB, then exercise local contracts.

Uses BENCH_DATABASE_URL and PILOT_REDIS_URL (DB13) from environment. Run with the
backend venv. No external network, existing DB mutation, image build or human test.
"""
import argparse
import base64
import os
import secrets
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse,urlunparse
import uuid
import psycopg
from psycopg import sql
from redis import Redis

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    dsn=os.environ['BENCH_DATABASE_URL'];redis_url=os.environ['PILOT_REDIS_URL']
    if any(urlparse(v).hostname not in {'127.0.0.1','localhost','::1'} for v in [dsn,redis_url]) or urlparse(redis_url).path!='/13':
        raise ValueError('Only loopback dependencies and separate RedisDB13 are allowed')
    redis=Redis.from_url(redis_url)
    if redis.dbsize():raise ValueError('RedisDB13 is not empty')
    run_id=uuid.uuid4().hex[:12];db='begamnagam_pilot_'+run_id
    with psycopg.connect(dsn,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db)))
    env=dict(os.environ,DATABASE_URL=urlunparse(urlparse(dsn)._replace(path='/'+db)),REDIS_URL=redis_url,
        CACHE_KEY_PREFIX='pilot:'+run_id,DEBUG='0',DEMO_MODE='1',DJANGO_TESTING='0',
        DJANGO_SECRET_KEY=secrets.token_urlsafe(48),PHONE_HASH_KEY=secrets.token_urlsafe(48),
        PHONE_ENCRYPTION_KEY=base64.urlsafe_b64encode(os.urandom(32)).decode(),
        CELERY_BROKER_URL='memory://',CELERY_TASK_ALWAYS_EAGER='1',PROVIDER_NETWORK_MODE='disabled',
        SMS_BACKEND='console',OTP_BACKEND='demo',PAYMENT_BACKEND='demo',AI_MODE='template',
        PILOT_POSITIVE_ONLY='0',SENDING_WINDOW_ENABLED='0',LIVE_PROVIDERS_ENABLED='0',LOCAL_REAL_OTP_ENABLED='0')
    folder=ROOT/'.local'/('pilot-'+run_id);folder.mkdir(parents=True)
    try:
        with (folder/'migrate.log').open('w') as log:
            subprocess.run([sys.executable,'manage.py','migrate','--noinput'],cwd=ROOT/'backend',env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
        subprocess.run([sys.executable,'manage.py','synthetic_pilot','--output',str(Path(args.output).resolve())],cwd=ROOT/'backend',env=env,check=True)
    finally:
        keys=list(redis.scan_iter(match='pilot:'+run_id+':*'))
        if keys:redis.delete(*keys)

if __name__=='__main__':main()
