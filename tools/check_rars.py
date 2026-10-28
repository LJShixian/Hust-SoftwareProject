"""Cross-check mycc against RARS: byte-exact assembly and identical behaviour.

Two independent claims are verified here, because the built-in encoder and the
codegen fallbacks are both easy to get subtly wrong:

* **encoding** — hand the `--rars` listing to the real assembler and compare the
  words it dumps with what `mycc/encode.py` produced;
* **behaviour** — run the same program built for the 22-instruction Logisim set
  and for unconstrained PF-01, and require identical output.

RARS is optional; when the jar or a JVM is missing both checks skip with exit 0 so
this can sit in a check script on machines without Java.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from mycc import core
from mycc.encode import assemble
from mycc.rars import convert

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = [
    Path(os.environ.get('MYCC_RARS_JAR', '')),
    ROOT / 'tools' / 'rars.jar',
    Path(r'D:\Desktop\2026秋硬件综合训练课设资料发布包\RISC-V汇编工具与测试用例5.0'
         r'\RISC-V汇编工具与测试用例5.0\rars_f0c874c.jar'),
]
PROFILES = {'logisim': ('logisim', 'logisim'), 'pf01': ('PF-01', 'generic'),
            'no-lui-vshift': ('PF-01', 'generic')}


def build(source, profile_name, target, disable=()):
    """Compile with the same policy the shipped listing uses.

    The Logisim target must go through its adapter: it is the bounded `%lo`
    address policy, not the generic PC-literal pool, that the hardware needs.
    """
    from adapters import compile_options
    profile = core.load_profile(profile_name, disable=list(disable))
    options = compile_options(target)
    return core.compile(core.SourceFile(source.read_text(encoding='utf-8-sig'), str(source)),
                        profile, options=options)


def find_jar():
    if not shutil.which('java'):
        return None
    for candidate in CANDIDATES:
        if str(candidate) and Path(candidate).is_file():
            return Path(candidate)
    return None


def rars_dump(jar, listing, out):
    # `mc` must come before `a`; CompactDataAtZero places data at address 0, the
    # layout the Logisim RAM uses, so absolute %hi/%lo resolve identically.
    result = subprocess.run(
        ['java', '-jar', str(jar), 'mc', 'CompactDataAtZero', 'a',
         'dump', '.text', 'HexText', str(out), str(listing)],
        capture_output=True, text=True, encoding='utf-8', errors='replace')
    if not out.exists():
        return None, (result.stdout + result.stderr).strip()[-500:]
    words = [int(line.strip(), 16) for line in out.read_text().splitlines()
             if re.fullmatch(r'[0-9a-fA-F]{8}', line.strip())]
    return words, None


def check_encoding(jar, sources, scratch):
    failures = []
    for label, (profile_name, target) in PROFILES.items():
        disable = ['lui', 'vshift'] if label == 'no-lui-vshift' else []
        for source in sources:
            result = build(source, profile_name, target, disable)
            if not result.success:
                failures.append(f'{source.name}: compile failed for {label}')
                continue
            listing = scratch / f'{source.stem}.{label}.asm'
            listing.write_text(convert(result.asm, profile=core.load_profile(profile_name, disable=disable)),
                               encoding='utf-8')
            ours, _, _ = assemble(listing.read_text(encoding='utf-8'))
            reference, error = rars_dump(jar, listing, scratch / f'{source.stem}.{label}.ref.hex')
            if reference is None:
                failures.append(f'{source.name} [{label}]: RARS rejected the listing: {error}')
            elif ours != reference:
                index = next((i for i, (a, b) in enumerate(zip(ours, reference)) if a != b), None)
                failures.append(f'{source.name} [{label}]: encoding differs at word {index} '
                                f'(ours vs rars, {len(ours)}/{len(reference)} words)')
    return failures


def check_behaviour(jar, sources, scratch):
    failures = []
    for source in sources:
        outputs = {}
        for label, profile_name in (('logislim', 'logisim'), ('baseline', 'PF-01')):
            target = 'logisim' if profile_name == 'logisim' else 'generic'
            result = build(source, profile_name, target)
            if not result.success:
                failures.append(f'{source.name}: compile failed for {profile_name}')
                break
            stack = 1024 if profile_name == 'logisim' else None
            listing = scratch / f'{source.stem}.{label}.run.asm'
            listing.write_text(convert(result.asm, profile=core.load_profile(profile_name),
                                       stack_top=stack), encoding='utf-8')
            run = subprocess.run(['java', '-jar', str(jar), 'mc', 'CompactDataAtZero', 'nc', 'me',
                                  str(listing)], capture_output=True, text=True,
                                 encoding='utf-8', errors='replace')
            outputs[label] = (run.returncode, (run.stdout or '').strip())
        if len(outputs) == 2 and outputs['logislim'] != outputs['baseline']:
            failures.append(f'{source.name}: output differs between the 22-instruction build and PF-01')
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='*')
    parser.add_argument('--jar', default=None)
    args = parser.parse_args(argv)
    jar = Path(args.jar) if args.jar else find_jar()
    if jar is None:
        print('rars: skipped (no JVM or rars.jar; set MYCC_RARS_JAR to enable)')
        return 0
    sources = [Path(p) for p in args.sources] or (sorted((ROOT / 'examples' / 'compiler').glob('*.c'))
                                                 + sorted((ROOT / 'examples' / 'logisim').glob('*.c')))
    scratch = ROOT / 'build' / 'rars-crosscheck'
    scratch.mkdir(parents=True, exist_ok=True)
    failures = check_encoding(jar, sources, scratch) + check_behaviour(jar, sources, scratch)
    for failure in failures:
        print('  ' + failure)
    print(f'rars: {len(sources)} program(s) x {len(PROFILES)} profiles encoded identically, '
          f'behaviour matched; {len(failures)} problem(s)')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
