"""Pre-flight check: will these programs load and run on the course Logisim CPU?

The classroom target has hard limits that a compiler cannot infer from the source:
a 1024-word instruction ROM, a 1024-byte data RAM, and a decoder that only knows
24 instructions. This tool rebuilds each example through the Logisim target,
decodes every emitted word itself (no objdump needed), and reports anything that
would fail on the bench instead of during the demo.
"""
import argparse
from pathlib import Path
import sys

from mycc import core
from mycc.encode import assemble, decode, HARDWARE_ONLY
from mycc.rars import convert

ROOT = Path(__file__).resolve().parents[1]
ROM_WORDS = 1024
RAM_BYTES = 1024


def check_source(source, out, profile):
    from adapters import compile_options
    # Use the adapter policy, not the generic one: the image that ships uses
    # bounded %lo addresses, so auditing the PC-literal build would check a
    # different program than the one loaded into the ROM.
    result = core.compile(core.SourceFile(source.read_text(encoding='utf-8-sig'), str(source)),
                          profile, options=compile_options('logisim'))
    if not result.success:
        raise RuntimeError(''.join(core.format_diagnostic(d) for d in result.diagnostics))
    listing = convert(result.asm, profile=profile, stack_top=ROM_WORDS)
    rom, ram, _ = assemble(listing)
    return listing, rom, ram


def check(sources=None, profile=None, quiet=False):
    """Return a list of human-readable problems; empty means the demo is safe."""
    profile = profile or core.load_profile('logisim')
    allowed = set(core.PRESETS['logisim']) | HARDWARE_ONLY | {'ecall'}
    sources = sources or sorted((ROOT / 'examples' / 'compiler').glob('*.c')) \
        + sorted((ROOT / 'examples' / 'logisim').glob('*.c'))
    problems = []
    rows = []
    for source in sources:
        source = Path(source)
        try:
            listing, rom, ram = check_source(source, None, profile)
        except Exception as exc:
            problems.append(f'{source.name}: {exc}')
            continue
        outside = sorted({decode(word) or f'0x{word:08x}' for word in rom} - allowed)
        notes = []
        if outside:
            notes.append('out-of-ISA: ' + ' '.join(outside))
        if len(rom) > ROM_WORDS:
            notes.append(f'ROM {len(rom)} > {ROM_WORDS} words')
        if len(ram) * 4 > RAM_BYTES:
            notes.append(f'RAM {len(ram) * 4} > {RAM_BYTES} bytes')
        if notes:
            problems.append(f'{source.name}: ' + '; '.join(notes))
        used = {decode(word) for word in rom} - {None}
        rows.append((source.name, len(rom), len(ram), len(used), notes))
    if not quiet:
        print(f'{"program":22s} {"ROM":>5} {"RAM":>4} {"isa":>4}')
        for name, rom_words, ram_words, used, notes in rows:
            flag = ' !' if notes else ''
            print(f'{name:22s} {rom_words:5d} {ram_words:4d} {used:4d}{flag}')
        for problem in problems:
            print('  ' + problem)
        print(f'logisim images: {len(rows)} program(s), ROM limit {ROM_WORDS} words, '
              f'RAM limit {RAM_BYTES} bytes, {len(problems)} problem(s)')
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='*')
    parser.add_argument('--profile', default='logisim')
    args = parser.parse_args(argv)
    try:
        profile = core.load_profile(args.profile, disable=[] if args.profile == 'logisim' else [])
    except core.ProfileError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return exc.exit_code
    problems = check([Path(p) for p in args.sources] or None, profile)
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
