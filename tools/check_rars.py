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

# RARS 1.5 builds a fresh InputStreamReader on every ReadChar, so the first call
# drains a redirected stream and the second one sees EOF. Console-fed programs are
# therefore fed from an array instead, which keeps `readint`/`readchar` and the
# scanf lowering under test. The seed text comes from `<name>.in` beside the source.
CONSOLE_SHIM = re.compile(r'getchar:\naddi a7,zero,12\necall\njalr zero,0\(ra\)')
ARRAY_SHIM = ('getchar:\n    la t0, __probe_input\n    la t1, __probe_index\n'
              '    lw t2, 0(t1)\n    add t0, t0, t2\n    lbu a0, 0(t0)\n'
              '    addi t2, t2, 1\n    sw t2, 0(t1)\n    jalr zero, 0(ra)')
TIMEOUT = 300


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
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        stdin=subprocess.DEVNULL, timeout=TIMEOUT)
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


def seed(source):
    """Text the program should read, or None when it needs a console we cannot give."""
    text = source.with_suffix('.in')
    return text.read_text(encoding='utf-8') if text.is_file() else None


def feed_console(listing, text):
    """Swap the getchar shim for one that walks a seeded array."""
    if not CONSOLE_SHIM.search(listing):
        return None
    escaped = (text.replace('\\', '\\\\').replace('\n', '\\n')
                   .replace('\t', '\\t').replace('"', '\\"'))
    return (CONSOLE_SHIM.sub(ARRAY_SHIM, listing, count=1)
            + f'\n.data\n__probe_input:\n.asciz "{escaped}"\n__probe_index:\n.word 0\n')


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
            text = convert(result.asm, profile=core.load_profile(profile_name), stack_top=stack)
            if 'jal ra,getchar' in text:
                data = seed(source)
                if data is None:
                    failures.append(f'{source.name}: reads the console but has no {source.stem}.in seed')
                    break
                text = feed_console(text, data)
            listing.write_text(text, encoding='utf-8')
            try:
                run = subprocess.run(
                    ['java', '-jar', str(jar), 'mc', 'CompactDataAtZero', 'nc', 'me', str(listing)],
                    capture_output=True, text=True, encoding='utf-8', errors='replace',
                    stdin=subprocess.DEVNULL, timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                failures.append(f'{source.name} [{label}]: RARS did not finish within {TIMEOUT}s')
                break
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
