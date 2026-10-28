"""Pre-flight check: will these programs load and run on the course Logisim CPU?

The classroom target has hard limits that a compiler cannot infer from the source:
a 1024-word instruction ROM, a 1024-byte data RAM, and a decoder that only knows
23 instructions. This tool rebuilds each example through the Logisim target,
decodes every emitted word itself (no objdump needed), and reports anything that
would fail on the bench instead of during the demo.
"""
import argparse
from pathlib import Path
import sys

from mycc import core
from mycc.encode import assemble
from mycc.rars import convert

ROOT = Path(__file__).resolve().parents[1]
ROM_WORDS = 1024
RAM_BYTES = 1024
TRAPS = {0x00000073: 'ecall', 0x00100073: 'ebreak', 0x30200073: 'mret', 0x00200073: 'uret'}
CSR = {1: 'csrrw', 2: 'csrrs', 3: 'csrrc', 5: 'csrrwi', 6: 'csrrsi', 7: 'csrrci'}
# Instructions the design report lists that mycc never emits.
HARDWARE_ONLY = {'divu', 'remu', 'csrrw', 'csrrsi', 'csrrci', 'uret'}

R_FUNCT = {(0x00, 0): 'add', (0x20, 0): 'sub', (0x00, 1): 'sll', (0x00, 2): 'slt',
           (0x00, 3): 'sltu', (0x00, 4): 'xor', (0x00, 5): 'srl', (0x20, 5): 'sra',
           (0x00, 6): 'or', (0x00, 7): 'and'}
I_FUNCT = {0: 'addi', 2: 'slti', 3: 'sltiu', 4: 'xori', 6: 'ori', 7: 'andi'}
LOAD_FUNCT = {0: 'lb', 1: 'lh', 2: 'lw', 4: 'lbu', 5: 'lhu'}
STORE_FUNCT = {0: 'sb', 1: 'sh', 2: 'sw'}
BRANCH_FUNCT = {0: 'beq', 1: 'bne', 4: 'blt', 5: 'bge', 6: 'bltu', 7: 'bgeu'}


def decode(word):
    """Return the mnemonic a decoder for this ISA would see, or None if unknown."""
    opcode = word & 0x7F
    funct3 = (word >> 12) & 0x7
    funct7 = (word >> 25) & 0x7F
    if opcode == 0x33:
        if funct7 == 0x01:
            return {5: 'divu', 7: 'remu'}.get(funct3)
        return R_FUNCT.get((funct7, funct3))
    if opcode == 0x13:
        if funct3 == 1:
            return 'slli'
        if funct3 == 5:
            return {0x00: 'srli', 0x20: 'srai'}.get(funct7)
        return I_FUNCT.get(funct3)
    if opcode == 0x03:
        return LOAD_FUNCT.get(funct3)
    if opcode == 0x23:
        return STORE_FUNCT.get(funct3)
    if opcode == 0x63:
        return BRANCH_FUNCT.get(funct3)
    if opcode == 0x6F:
        return 'jal'
    if opcode == 0x67:
        return 'jalr' if funct3 == 0 else None
    if opcode == 0x37:
        return 'lui'
    if opcode == 0x17:
        return 'auipc'
    if opcode == 0x73:
        if funct3:
            return CSR.get(funct3)
        return TRAPS.get(word)
    return None


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
