#!/usr/bin/env python3
"""Validate before creating the ZIP; use only the validated package file set."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import zipfile

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, "-B", str(root / "qa/validate-package.py")],
               check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
destination = root.parent / "begam-nagam-itools-product.zip"
with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            archive.write(path, "begam-nagam/" + path.relative_to(root).as_posix())
with zipfile.ZipFile(destination) as archive:
    assert archive.testzip() is None, "ZIP CRC validation failed"
digest = hashlib.sha256(destination.read_bytes()).hexdigest()
destination.with_suffix(".zip.sha256").write_text(f"{digest}  {destination.name}\n")
print(f"{destination.name}: {destination.stat().st_size} bytes; SHA-256 {digest}")
