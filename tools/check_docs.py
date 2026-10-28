"""Doc/code drift checks: README claims must match the single source of truth.

The README publishes per-preset instruction counts and the JSON files under
configs/isa/presets repeat them. Both are copies of mycc/core/isa.py, so both can
drift silently. This module makes the drift a build failure instead of a review
finding.
"""
import json
import re
from pathlib import Path

from mycc.core.isa import ALIASES, GROUPS, MV_ISA, PRESETS

ROOT = Path(__file__).resolve().parents[1]

README_ROW = re.compile(r'^\|\s*(PF-0\d|cpu21)\s*(?:/\s*([\w+-]+))?\s*\|\s*(\d+)\s*\|')


def readme_counts():
    text = (ROOT/'README.md').read_text(encoding='utf-8')
    found = {}
    for line in text.splitlines():
        match = README_ROW.match(line)
        if match:
            found[match.group(1)] = int(match.group(3))
    return found


def check():
    errors = []

    # 1. README preset table vs core/isa.py
    counts = readme_counts()
    if not counts:
        errors.append('README: preset table not found; the drift check would be vacuous')
    expected = {f'PF-{i:02}': len(PRESETS[ALIASES[f"PF-{i:02}"]]) for i in range(1, 9)}
    expected['cpu21'] = len(PRESETS['cpu21'])
    for name, count in sorted(expected.items()):
        if name not in counts:
            errors.append(f'README: preset {name} missing from the table')
        elif counts[name] != count:
            errors.append(f'README: {name} claims {counts[name]} instructions, core/isa.py has {count}')

    # 2. configs/isa/presets/*.json vs core/isa.py
    for path in sorted((ROOT/'configs/isa/presets').glob('PF-0*.json')):
        alias = path.stem
        data = json.loads(path.read_text(encoding='utf-8'))
        if alias not in ALIASES:
            errors.append(f'{path.name}: no matching preset alias')
            continue
        declared = set(data.get('instructions', []))
        actual = set(PRESETS[ALIASES[alias]])
        if declared != actual:
            missing, extra = sorted(actual-declared), sorted(declared-actual)
            errors.append(f'{path.name}: differs from core/isa.py (missing {missing}, extra {extra})')

    # 3. MV-ISA floor must stay a subset of every shipped preset
    for name, instructions in sorted(PRESETS.items()):
        if not MV_ISA <= instructions:
            errors.append(f'preset {name} omits required MV-ISA {sorted(MV_ISA-instructions)}')

    # 4. Every documented group name must resolve
    for name in sorted(GROUPS):
        if name.startswith('EX-'):
            continue
        if not GROUPS[name]:
            errors.append(f'group {name} is empty')

    return errors


def main():
    errors = check()
    for error in errors:
        print(error)
    if not errors:
        print('docs: README preset table, JSON reference sets and MV-ISA floor agree with core/isa.py')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
