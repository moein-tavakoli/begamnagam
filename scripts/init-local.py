#!/usr/bin/env python3
"""Create local demo secrets without replacing an existing .env file."""
import base64
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent.parent
target = ROOT / ".env"
if target.exists():
    print(".env already exists; preserved without changes.")
    raise SystemExit(0)

values = {
    "DJANGO_SECRET_KEY": secrets.token_urlsafe(48),
    "PHONE_HASH_KEY": secrets.token_urlsafe(48),
    "PHONE_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "POSTGRES_PASSWORD": secrets.token_hex(24),
    "RABBITMQ_PASSWORD": secrets.token_hex(24),
}
content = (ROOT / ".env.example").read_text(encoding="utf-8")
lines = []
for line in content.splitlines():
    key = line.partition("=")[0]
    lines.append(f"{key}={values[key]}" if key in values else line)
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print(".env was created concurrently; preserved without changes.")
else:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print("Created .env with private local demo keys (permissions 0600).")
