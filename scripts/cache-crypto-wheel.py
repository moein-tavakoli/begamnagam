"""Optional official Linux wheel cache for slow networks; no TLS bypass or pin change."""
import hashlib
import json
import platform
from pathlib import Path
import subprocess
from urllib.parse import urlparse

def download(url):
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in {"pypi.org", "files.pythonhosted.org"}:
        raise SystemExit("Unexpected artifact host")
    return subprocess.check_output(["curl", "--fail", "--silent", "--show-error", "--max-time", "120", url])

machine = platform.machine().lower()
arch = 'aarch64' if machine in {'arm64','aarch64'} else 'x86_64' if machine in {'amd64','x86_64'} else None
if not arch: raise SystemExit('Unsupported cache architecture; use normal pip resolution')
metadata=json.loads(download('https://pypi.org/pypi/cryptography/46.0.7/json'))
filename=f'cryptography-46.0.7-cp311-abi3-manylinux_2_34_{arch}.whl'
artifact=next(row for row in metadata['urls'] if row['filename']==filename)
folder=Path(__file__).resolve().parent.parent/'backend/wheels'
folder.mkdir(exist_ok=True)
target=folder/filename
if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=artifact['digests']['sha256']:
    data=download(artifact['url'])
    if hashlib.sha256(data).hexdigest()!=artifact['digests']['sha256']: raise SystemExit('Checksum mismatch; refusing artifact')
    target.write_bytes(data)
print(f'Verified official wheel: {filename}')
