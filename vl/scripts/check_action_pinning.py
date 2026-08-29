#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path('.github/workflows')
USE_RE = re.compile(r'^\s*-?\s*uses:\s*([^\s#]+)', re.M)
FULL_SHA = re.compile(r'^[0-9a-fA-F]{40}$')

findings = []
for path in sorted(ROOT.glob('*.y*ml')):
    text = path.read_text(encoding='utf-8')
    for lineno, line in enumerate(text.splitlines(), 1):
        m = USE_RE.match(line)
        if not m:
            continue
        target = m.group(1)
        if target.startswith('./') or target.startswith('docker://'):
            continue
        if '@' not in target:
            findings.append((path, lineno, target, 'missing @ref'))
            continue
        action, ref = target.rsplit('@', 1)
        if not FULL_SHA.fullmatch(ref):
            findings.append((path, lineno, target, 'mutable/non-SHA ref'))

print(f'Scanned {len(list(ROOT.glob("*.y*ml")))} workflow files.')
if findings:
    print(f'UNPINNED_ACTION_REFERENCES={len(findings)}')
    for path, lineno, target, reason in findings:
        print(f'{path}:{lineno}: {target} [{reason}]')
    sys.exit(1)

print('UNPINNED_ACTION_REFERENCES=0')
print('ACTION_PINNING_AUDIT=PASS')
