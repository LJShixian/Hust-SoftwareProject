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

# name -> (ecall number, argument register already holding the value)
SHIMS = {
    'putchar': 11,    # print char, a0
    'printint': 1,    # print int, a0
    'printhex': 34,   # print hex, a0
    'exit': 17,       # exit2, a0 = exit code
}

# Measured on the real circuit: a7==34 displays a0 and CONTINUES; any other a7
# halts and waits for `go`. The reference benchmark carries 32 display ecalls and
# only 5 halting ones (a7=10), so a halt is an explicit section boundary rather
# than a property of ecall itself. The image therefore maps printhex/printint to
# a7=34 (hex is the only display this CPU has), putchar to a no-op (no character
# display), and exit to a7=10, which is how a C program asks for a checkpoint.
HARDWARE_HALT = 10
HARDWARE_DISPLAY = 34
HARDWARE_SHIMS = {
    'putchar': None,                      # no character display on this CPU
    'printint': HARDWARE_DISPLAY,         # hex is the only display this CPU has
    'printhex': HARDWARE_DISPLAY,
    'exit': HARDWARE_HALT,
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
    if number is None:
        # A no-op keeps the call site valid without an ecall that would halt.
        return f'.globl {name}\n{name}:\njalr zero,0(ra)'
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


def convert(asm, profile=None, runtime=True, stack_top=None, hardware_io=False):
    """Return a single-file RARS listing equivalent to the GNU assembly `asm`."""
    body = asm
    if runtime and RUNTIME.exists():
        body += '\n' + RUNTIME.read_text(encoding='utf-8')
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
    table = HARDWARE_SHIMS if hardware_io else SHIMS
    shims = [_shim(name, number) for name, number in table.items()
             if name in used and name not in defined]
    if shims:
        out += '\n# --- RARS syscall shims ---\n' + '\n\n'.join(shims) + '\n'
    return out


def images(asm, profile=None, runtime=True, stack_top=None, hardware_io=True):
    """Return (listing, rom_words, ram_words): a Logisim ROM/RAM image pair."""
    text = convert(asm, profile=profile, runtime=runtime, stack_top=stack_top,
                   hardware_io=hardware_io)
    rom_words, ram_words, _ = assemble(text)
    return text, rom_words, ram_words


def rom_hex(words):
    return hex_image(words)


def ram_hex(words):
    return hex_image(words)
