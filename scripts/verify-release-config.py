#!/usr/bin/env python3
"""Validate release topology with synthetic placeholders; never starts containers."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='begamnagam-release-config-') as folder:
    config = Path(folder)/'config.env'
    config.write_text((root/'deploy/release.env.example').read_text())
    config.chmod(0o600)
    result = subprocess.run(['docker','compose','--env-file',str(config),'-f',str(root/'compose.release.yaml'),'config','--format','json'],
        env=dict(os.environ,RELEASE_ENV_FILE=str(config)),capture_output=True,text=True,cwd=root)
    if result.returncode:
        raise SystemExit('Release Compose validation failed (no configuration/secrets printed)')
    services = json.loads(result.stdout)['services']
    assert all(not value.get('ports') for name,value in services.items() if name!='proxy')
    assert not any(value.get('build') or value.get('privileged') or value.get('network_mode')=='host' for value in services.values())
    for name in ['backend','worker','beat','migrate']:
        assert services[name]['environment']['DEBUG']=='0'
        assert services[name]['environment']['DEMO_MODE']=='0'
        assert services[name]['environment']['DJANGO_SETTINGS_MODULE']=='config.release_settings'
    assert set(services['proxy']['ports'][i]['target'] for i in range(len(services['proxy']['ports'])))=={80,443}
print('PASS: isolated release topology; images, public TLS and deployment remain unapproved')
