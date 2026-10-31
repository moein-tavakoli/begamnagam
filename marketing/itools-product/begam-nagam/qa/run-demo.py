#!/usr/bin/env python3
"""Reproduce the explicitly authorized, isolated screenshot demo. No live providers."""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys

SOURCE_COMMIT = "4c1ffceae5b10421b0f2f0fc134f402ead270b8b"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--runtime", type=Path, required=True)
args = parser.parse_args()
repo, runtime = args.repo.resolve(), args.runtime.resolve()
if runtime == repo or (runtime.exists() and any(runtime.iterdir())):
    raise SystemExit("Use a new isolated runtime directory; never reuse a product database.")
for port in (3137, 8137):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Port {port} is occupied. Leave its existing service untouched.")
runtime.mkdir(parents=True, exist_ok=True)
runtime.chmod(0o700)
if not (runtime / "backend/manage.py").exists():
    archive = subprocess.Popen(["git", "archive", SOURCE_COMMIT], cwd=repo, stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(runtime)], stdin=archive.stdout, check=True)
    archive.stdout.close()
    if archive.wait():
        raise SystemExit("Source export failed")
if not (runtime / "frontend/node_modules").exists():
    source_modules = repo / "frontend/node_modules"
    if not source_modules.is_dir():
        raise SystemExit("Install the repository's locked frontend dependencies first.")
    if sys.platform == "darwin":
        subprocess.run(["cp", "-cR", str(source_modules), str(runtime / "frontend/node_modules")], check=True)
    else:
        shutil.copytree(source_modules, runtime / "frontend/node_modules")
python = repo / "backend/.venv/bin/python"
if not python.exists():
    raise SystemExit("Install backend/requirements.lock.txt in backend/.venv first.")
common = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG") if key in os.environ}
env = {**common,
    "DJANGO_SETTINGS_MODULE": "config.settings", "DEBUG": "1", "DEMO_MODE": "1",
    "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
    "PHONE_HASH_KEY": secrets.token_urlsafe(48),
    "PHONE_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
    "CSRF_TRUSTED_ORIGINS": "http://127.0.0.1:3137,http://localhost:3137",
    "APP_BASE_URL": "https://demo.invalid", "OTP_BACKEND": "demo",
    "LOCAL_REAL_OTP_ENABLED": "0", "SMS_BACKEND": "console", "PAYMENT_BACKEND": "demo",
    "PROVIDER_NETWORK_MODE": "disabled", "LIVE_PROVIDERS_ENABLED": "0",
    "PROVIDER_ENVIRONMENT": "sandbox", "PROVIDER_DAILY_BUDGET_UNLIMITED": "0",
    "PROVIDER_DAILY_BUDGET_RIAL": "0", "SMS_MAX_COST_RIAL": "0", "OTP_MAX_COST_RIAL": "0",
    "AI_MODE": "template", "GAPGPT_API_KEY": "", "KAVENEGAR_API_KEY": "",
    "KAVENEGAR_SENDER": "", "ZARINPAL_MERCHANT_ID": "",
    "GAPGPT_DAILY_REQUEST_LIMIT": "0", "GAPGPT_USER_DAILY_LIMIT": "0",
    "GAPGPT_DAILY_REQUEST_UNLIMITED": "0", "DEMO_TEST_TOOLS_ENABLED": "0",
    "DATABASE_URL": "", "REDIS_URL": "", "CELERY_TASK_ALWAYS_EAGER": "1",
    "CELERY_BROKER_URL": "memory://", "SENDING_WINDOW_ENABLED": "0", "PILOT_POSITIVE_ONLY": "0",
}
# Private local diagnostic state, outside the delivery package. Delete after capture.
env_file = runtime / "runtime-env.json"
env_file.write_text(json.dumps(env))
env_file.chmod(0o600)
subprocess.run([str(python), "manage.py", "migrate", "--noinput"], cwd=runtime / "backend", env=env, check=True)
children = []
try:
    api_log = open(runtime / "api.log", "w")
    web_log = open(runtime / "web.log", "w")
    children.append(subprocess.Popen([str(python), "manage.py", "runserver", "127.0.0.1:8137", "--noreload"],
        cwd=runtime / "backend", env=env, stdout=api_log, stderr=subprocess.STDOUT, start_new_session=True))
    web_env = {**common, "INTERNAL_API_URL": "http://127.0.0.1:8137",
        "APP_BASE_URL": "http://127.0.0.1:3137", "SEO_INDEXABLE": "0", "NEXT_TELEMETRY_DISABLED": "1"}
    children.append(subprocess.Popen(["npm", "run", "dev", "--", "--port", "3137"],
        cwd=runtime / "frontend", env=web_env, stdout=web_log, stderr=subprocess.STDOUT, start_new_session=True))
    print("Isolated demo: http://127.0.0.1:3137 | capture source 0.16.1 / " + SOURCE_COMMIT, flush=True)
    print("OTP=demo; SMS/invitations=console; payments=demo; AI=template; external providers disabled.", flush=True)
    children[0].wait()
except KeyboardInterrupt:
    pass
finally:
    for child in children:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
    env_file.unlink(missing_ok=True)
    print("Stopped screenshot servers. Delete this isolated runtime to invalidate all synthetic sessions and grants.", flush=True)
