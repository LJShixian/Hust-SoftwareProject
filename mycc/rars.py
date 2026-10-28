"""Self-contained assembly for RARS, the simulator used by the hardware course.

RARS is not a GNU assembler and there is no link step, so the file that
``tools.build`` hands to ``as``/``ld`` cannot be loaded there. ``convert`` rewrites
a compiler listing into one file that RARS accepts and can run:

* ``.section .text`` becomes ``.text`` (RARS rejects a dotted section name),
  ``.bss`` becomes ``.data`` (RARS has no bss segment);
* directives RARS does not implement (``.option``, ``.type``, ``.size``,
  ``.balign``, ``.zero``) are dropped or translated to ``.align``/``.space``;
* the software arithmetic helpers from ``runtime/runtime.s`` are inlined *and*
  lowered against the selected profile, so a listing for a reduced instruction set
  never contains an instruction that machine cannot execute;
* data directives move into ``.data`` even when the compiler emitted them inside
  ``.text`` (a ``switch`` jump table lands there), because RARS rejects ``.word``
  in a text segment and a Harvard ROM cannot be read back by ``lw``;
* ``putchar``/``printint``/``printhex``/``exit`` become ecall shims;
* a ``main`` wrapper calls the compiled ``main`` and exits, because a RARS program
  starts at ``main`` with no caller to return to. The wrapper also loads ``sp``
  when a stack top is given: the classroom CPU resets every register to zero, so
  a program that inherits ``sp`` from a simulator would push onto 0xFFFFFFxx.

The conversion is deliberately a frontend-side text pass: the compiler keeps
emitting GNU assembly, and nothing in ``mycc.core`` gains file access.
"""
import re
from pathlib import Path

from .core import lower_assembly
from .core.codegen import MINIMAL_HELPERS
from .encode import assemble, hex_image

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime' / 'runtime.s'

# Data directives that RARS only accepts in the data segment.
DATA_DIRECTIVES = ('.word', '.byte', '.half', '.space', '.string', '.asciiz', '.float', '.double')

# Platform syscall ABI, the RISC-V convention every toolchain here shares:
#   a7 = service number, arguments in a0.., result returned in a0.
# The compiler only needs the three primitives below. `printint` and `printhex`
# are ordinary C in `runtime/io.c` and are layered on top of `putchar`, which is
# how a C library normally sits on a platform port.
SYSCALL_PRINT_CHAR = 11
SYSCALL_READ_CHAR = 12
SYSCALL_EXIT = 10
SHIMS = {
    'putchar': SYSCALL_PRINT_CHAR,   # a0 = character
    'getchar': SYSCALL_READ_CHAR,    # result in a0
    'exit': SYSCALL_EXIT,            # a0 = exit status
}

ENTRY = """\
# --- RARS entry: the simulator starts at main, so it needs a caller ---
.text
.globl main
main:
jal ra,__mycc_main
addi a7,zero,10
ecall
"""

LABEL = re.compile(r'(?m)^([A-Za-z_.$][\w.$]*):')
CALL = re.compile(r'(?m)^\s*jal\s+(?:ra|zero|[a-z]\d+)\s*,\s*([A-Za-z_.$][\w.$]*)')
SINGLE_LABEL = re.compile(r'^([A-Za-z_.$][\w.$]*):$')
LOCAL_LABEL = re.compile(r'\.L[\w.$]*')
BLOCK = re.compile(r'(?m)^\.globl\s+(\S+)\s*$')
DEFINED = re.compile(r'(?m)^([A-Za-z_.$][\w.$]*):')


def _relabel(text, prefix):
    """Prefix the assembler-local labels of one translation unit.

    Codegen numbers local labels per unit (`.Lreturn_1`, `.Lloop_2`, ...), which is
    safe across separate object files but collides when several units are inlined
    into one listing. Only `.L` names are touched; function symbols stay global.
    """
    return LOCAL_LABEL.sub(lambda match: f'.L{prefix}{match.group(0)[2:]}', text)


def _drop_unreferenced(text, external=''):
    """Drop `.globl` blocks that nothing outside them refers to.

    This is the single-file equivalent of the linker's section garbage collection:
    `runtime.s` also ships helpers a program never calls, and a 1024-word ROM
    cannot afford them. A block survives when its exported name *or any label it
    defines* is still referenced outside it, so a block that also hosts a shared
    subroutine keeps it when a sibling needs it.
    """
    parts = BLOCK.split(text)
    if len(parts) < 3:
        return text
    preamble, segments = parts[0], list(zip(parts[1::2], parts[2::2]))
    while True:
        for index, (name, block) in enumerate(segments):
            outside = external + preamble + ''.join(body for other, (_n, body) in enumerate(segments)
                                                    if other != index)
            symbols = [name, *DEFINED.findall(block)]
            # `\b` does not fire at the dot of `.Lfoo` (both sides are non-word
            # characters), so use an explicit boundary instead.
            if not any(re.search(rf'(?<![\w.$]){re.escape(symbol)}(?![\w.$])', outside)
                       for symbol in symbols):
                segments.pop(index)
                break
        else:
            break
    return preamble + ''.join(f'.globl {name}{body}' for name, body in segments)


def _rewrite(line):
    """Translate one source line; return None to drop it."""
    text = line.strip()
    if not text:
        return line
    if text.startswith('.option') or text.startswith('.type') or text.startswith('.size'):
        return None
    match = re.match(r'\.section\s+(\S+)', text)
    if match:
        return '.text' if match.group(1).lstrip('.') == 'text' else '.data'
    match = re.match(r'\.balign\s+(\d+)', text)
    if match:
        size = int(match.group(1))
        if size > 0 and size & (size - 1) == 0:
            return f'.align {size.bit_length() - 1}'
        return None
    match = re.match(r'\.zero\s+(\d+)', text)
    if match:
        return f'.space {match.group(1)}'
    return line


def _shim(name, number):
    return f'.globl {name}\n{name}:\naddi a7,zero,{number}\necall\njalr zero,0(ra)'


def _head(line):
    text = line.strip()
    if not text or text.startswith('#'):
        return ''
    return text.split()[0]


def _sectionize(lines):
    """Give every item the section RARS requires, inserting `.text`/`.data` runs.

    A label takes the section of the next real item, so a jump-table label stays
    with its `.word` when the whole table moves into the data segment.
    """
    kinds = []
    for line in lines:
        head = _head(line)
        if head in ('.text', '.data') or head.startswith('.section'):
            kinds.append(('section', head.lstrip('.').split('.')[-1], line))
        elif head in DATA_DIRECTIVES:
            kinds.append(('data', None, line))
        elif not head:
            kinds.append(('blank', None, line))
        elif head.startswith('.'):
            kinds.append(('directive', None, line))
        elif SINGLE_LABEL.match(line.strip()) or head.endswith(':'):
            kinds.append(('label', None, line))
        else:
            kinds.append(('instruction', None, line))
    desired = [None] * len(kinds)
    current = 'text'
    for index in range(len(kinds) - 1, -1, -1):
        kind, name, _ = kinds[index]
        if kind == 'data':
            current = 'data'
        elif kind == 'instruction':
            current = 'text'
        elif kind == 'section' and name in ('text', 'data'):
            current = name
        if kind in ('data', 'instruction', 'directive', 'label'):
            desired[index] = current
    out = []
    emitted = None
    for (kind, name, line), want in zip(kinds, desired):
        if kind == 'section':
            # The backward pass already used the explicit marker to decide
            # `want`; re-emitting it here would suppress the switch line that
            # the following items still need.
            if name not in ('text', 'data'):
                out.append(line)
            continue
        if kind == 'blank':
            out.append(line)
            continue
        if want and want != emitted:
            out.append('.' + want)
            emitted = want
        out.append(line)
    return out


def _stack_init(stack_top, profile):
    """Instructions that load `sp`, using only what the profile guarantees."""
    if stack_top is None:
        return []
    if not 0 <= stack_top <= 0xFFFFFFFF:
        raise ValueError(f'stack top {stack_top} is not a 32-bit address')
    if stack_top <= 2047:
        return [f'addi sp,zero,{stack_top}']
    if profile is not None and profile.has('lui'):
        low = stack_top & 0xFFF
        if low >= 0x800:
            low -= 0x1000
        high = ((stack_top - low) >> 12) & 0xFFFFF
        return [f'lui sp,{high}', f'addi sp,sp,{low}']
    raise ValueError(f'stack top {stack_top} needs lui, which this profile disables; '
                     'choose an address below 2048')


def _entry(stack_top, profile):
    lines = ['# --- RARS entry: the simulator starts at main, so it needs a caller ---',
             '.text', '.globl main', 'main:']
    lines.extend(_stack_init(stack_top, profile))
    lines.extend(['jal ra,__mycc_main', 'addi a7,zero,10', 'ecall'])
    return '\n'.join(lines) + '\n'


# C sources that make up the platform port. `input.c` is separate because it
# needs a console, which the board and CPU21 runtimes do not provide.
PORT_SOURCES = ('io.c', 'input.c')


def _io_unit(profile):
    """Compile the C half of the platform port.

    `printint`/`printhex`/`printstr` are ordinary C layered on `putchar`, exactly
    as a C library sits on top of a platform's character primitive. Keeping them in
    C means the simulator and the board run the same library code.
    """
    from .core import CompileOptions, SourceFile, compile as compile_source
    units = []
    for name in PORT_SOURCES:
        path = ROOT / 'runtime' / name
        if not path.exists():
            continue
        result = compile_source(SourceFile(path.read_text(encoding='utf-8'), f'<runtime/{name}>'),
                                profile, options=CompileOptions(require_main=False))
        if not result.success:
            raise ValueError(''.join(result.diagnostics))
        units.append(result.asm)
    return units


def convert(asm, profile=None, runtime=True, stack_top=None, extra_units=()):
    """Return a single-file listing equivalent to the GNU assembly `asm`.

    With `runtime` the C library unit and the handwritten helper library are
    inlined. Their local labels get a per-unit prefix and any block nothing
    references is dropped, which is what the linker would otherwise do through
    separate object files.
    """
    if profile is None:
        from .core import load_profile
        profile = load_profile()
    units = list(extra_units)
    if runtime:
        # Each C file is its own unit: codegen numbers local labels from 1, so two
        # files merged first and relabelled later would collide.
        units = _io_unit(profile) + units
    body = asm
    for index, unit in enumerate(units, start=1):
        body += '\n' + _drop_unreferenced(_relabel(unit, f'u{index}_'), external=body)
    if runtime and RUNTIME.exists():
        body += '\n' + _drop_unreferenced(RUNTIME.read_text(encoding='utf-8'), external=body)
    # Keep the visible entry name for RARS while the compiled main keeps its body.
    body = re.sub(r'(?m)^\.globl\s+main\b', '.globl __mycc_main', body)
    body = re.sub(r'(?m)^main:', '__mycc_main:', body)
    if profile is not None:
        # Re-lower the whole listing so the handwritten runtime obeys the profile
        # too; drop the compiler's helper copy first or the labels collide.
        body = body.replace(MINIMAL_HELPERS, '')
        body = lower_assembly(body, profile)
    lines = [line for line in (_rewrite(x) for x in body.splitlines()) if line is not None]
    text = '\n'.join(_sectionize(lines)) + '\n'
    defined = set(LABEL.findall(text))
    used = set(CALL.findall(text))
    out = _entry(stack_top, profile) + '\n' + text
    shims = [_shim(name, number) for name, number in SHIMS.items()
             if name in used and name not in defined]
    if shims:
        out += '\n# --- RARS syscall shims ---\n' + '\n\n'.join(shims) + '\n'
    return out


def images(asm, profile=None, runtime=True, stack_top=None, extra_units=()):
    """Return (listing, rom_words, ram_words): a Logisim ROM/RAM image pair."""
    text = convert(asm, profile=profile, runtime=runtime, stack_top=stack_top,
                   extra_units=extra_units)
    rom_words, ram_words, _ = assemble(text)
    return text, rom_words, ram_words


def rom_hex(words):
    return hex_image(words)


def ram_hex(words):
    return hex_image(words)
