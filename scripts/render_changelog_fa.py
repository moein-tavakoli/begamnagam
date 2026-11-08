#!/usr/bin/env python3
"""Render the human Persian changelog from the private staff catalog."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'backend/core/release_notes.fa.json'
TARGET = ROOT / 'CHANGELOG.fa.md'


def render(catalog):
    lines = ['# تاریخچهٔ تغییرات فارسی', '',
             'خلاصهٔ فارسی نسخه‌های ثبت‌شده برای مدیران؛ جزئیات فنی و شواهد در [CHANGELOG.md](CHANGELOG.md) نگهداری می‌شوند.', '',
             catalog['notice'], '',
             'این فایل از `backend/core/release_notes.fa.json` تولید می‌شود و از مسیر عمومی وب ارائه نمی‌شود.', '']
    for entry in catalog['entries']:
        lines.extend([f"## {entry['version']} — {entry['title']}", ''])
        if entry['date']:
            lines.extend([f"تاریخ ثبت: {entry['date']}", ''])
        lines.extend(['وضعیت: نسخهٔ محلی؛ ثبت این شرح به معنی استقرار نیست.' if entry['scope'] == 'local'
                      else 'وضعیت: سابقهٔ نسخه؛ وضعیت نصب در این صفحه احراز نشده است.', ''])
        lines.extend(f'- {change}' for change in entry['changes'])
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    catalog = json.loads(SOURCE.read_text(encoding='utf-8'))
    versions = [entry['version'] for entry in catalog['entries']]
    recorded = re.findall(r'^## (\d+\.\d+\.\d+)\b', (ROOT/'CHANGELOG.md').read_text(encoding='utf-8'), re.M)
    if set(recorded) != set(versions):
        raise SystemExit('Persian and technical changelog versions differ')
    if len(versions) != len(set(versions)) or versions != sorted(versions,key=lambda v:tuple(map(int,v.split('.'))),reverse=True):
        raise SystemExit('Persian changelog versions must be unique and ordered')
    package = json.loads((ROOT/'frontend/package.json').read_text(encoding='utf-8'))
    if versions[0] != catalog['catalog_version'] or versions[0] != package['version']:
        raise SystemExit('Persian changelog and application version differ')
    text = render(catalog)
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding='utf-8') != text:
            raise SystemExit('Persian changelog is out of date; run python3 scripts/render_changelog_fa.py')
        print('Persian changelog matches its source')
    else:
        TARGET.write_text(text, encoding='utf-8')
        print('Rendered CHANGELOG.fa.md')


if __name__ == '__main__':
    main()
