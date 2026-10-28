#!/usr/bin/env python3
"""Verify the official Linux runtime and prepare a CPU-only Docker build context."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path, PurePosixPath

VERSION = '0.40.11'
SHA256 = '7bedab90dd122661be78798e9f0edf37fccf0cccf2699d2c58ea1a3afdc04b6d'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='Official ollama-linux-amd64.tar.zst for v'+VERSION)
    parser.add_argument('--output', type=Path, default=Path('.local/ollama-cpu-build'))
    args = parser.parse_args()
    checksum = hashlib.sha256()
    with args.archive.open('rb') as source:
        for data in iter(lambda: source.read(1024**2), b''):
            checksum.update(data)
    if checksum.hexdigest() != SHA256:
        raise SystemExit('Official runtime SHA256 does not match; nothing was installed.')
    if args.output.exists():
        raise SystemExit('Build context already exists; choose a new --output directory.')
    names = subprocess.check_output(['tar', '--zstd', '-tf', str(args.archive)], text=True).splitlines()
    if any(PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts for name in names):
        raise SystemExit('Unexpected archive paths.')
    runtime = args.output/'runtime'
    runtime.mkdir(parents=True)
    subprocess.run(['tar', '--zstd', '-xf', str(args.archive), '-C', str(runtime),
        '--exclude=*cuda*', '--exclude=*rocm*', '--exclude=*vulkan*', '--exclude=*mlx*', '--no-same-owner'], check=True)
    if not (runtime/'bin/ollama').is_file() or not (runtime/'lib/ollama').is_dir():
        raise SystemExit('Unexpected runtime layout; do not build this context.')
    recipe = Path(__file__).resolve().parents[1]/'deploy/ollama-cpu.Dockerfile'
    shutil.copyfile(recipe, args.output/'Dockerfile')
    (args.output/'verified-runtime.json').write_text(json.dumps({'version': VERSION, 'sha256': SHA256}, indent=2)+'\n')
    print(json.dumps({'context': str(args.output.resolve()), 'version': VERSION, 'sha256_verified': True}))


if __name__ == '__main__':
    main()
