#!/usr/bin/env python3
"""Fail a frontend candidate and restore the pinned image in begamnagam-g6 only.

Needs the already-running, disposable demo release-verification project. Never
touches localhost3000, migrations, providers, data volumes or another project.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
PROJECT = 'begamnagam-g6'
env = dict(os.environ, WEB_PORT='3080', API_PORT='8088', APP_BASE_URL='http://localhost:3080', DOCKER_SUBNET='10.253.243.0/24')
base = ['docker','compose','-p',PROJECT,'-f',str(ROOT/'compose.yaml'),'-f',str(ROOT/'.local/phase-two-clean.yaml')]


def run(command):
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError('Local rollback command failed; diagnostics withheld')
    return result.stdout


def inspect(name):
    return json.loads(run(['docker','inspect',PROJECT+'-'+name+'-1']))[0]


def watermark():
    return run([*base,'exec','-T','postgres','sh','-c',
        'exec psql -X -A -t -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*),COALESCE(max(id::text),chr(48)) FROM core_financialevent;"']).strip()


backend = inspect('backend')
assert 'DEMO_MODE=1' in backend['Config']['Env']
frontend = inspect('frontend')
assert frontend['NetworkSettings']['Ports']['3000/tcp'] == [{'HostIp':'127.0.0.1','HostPort':'3080'}]
known_good = frontend['Image']
before = watermark()
started = time.monotonic()
failed = False
with tempfile.TemporaryDirectory(prefix='begamnagam-rollback-') as folder:
    override = Path(folder)/'fault.json'
    override.write_text(json.dumps({'services':{'frontend':{'image':known_good,'command':['node','-e','process.exit(23)'],'restart':'no'}}}))
    try:
        run([*base,'-f',str(override),'up','--no-build','--no-deps','-d','frontend'])
        for _ in range(20):
            state = inspect('frontend')['State']
            if state['Status'] == 'exited':
                failed = state['ExitCode'] == 23
                break
            time.sleep(0.5)
        assert failed, 'Injected candidate did not fail as expected'
    finally:
        # Even if the assertion fails, restore the original immutable image ID.
        override.write_text(json.dumps({'services':{'frontend':{'image':known_good}}}))
        run([*base,'-f',str(override),'up','--no-build','--no-deps','-d','--wait','--wait-timeout','120','frontend'])

assert inspect('frontend')['Image'] == known_good
with urllib.request.urlopen('http://127.0.0.1:3080/', timeout=10) as response:
    assert response.status == 200
assert before == watermark()
report = {'kind':'isolated_local_failed_candidate_recovery','project':PROJECT,
    'injected_frontend_exit_code':23,'failed_candidate_observed':failed,
    'restored_exact_image_id':known_good,'health_and_homepage_recovered':True,
    'financial_watermark_unchanged':True,'migrations_reversed':False,
    'duration_seconds':round(time.monotonic()-started,3),
    'cross_version_browser_assets_tested':False,'public_rollout_tested':False,'passed':True}
(ROOT/'docs/release-v0.7/ROLLBACK.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
