"""Self-contained assembly for RARS, the simulator used by the hardware course.

RARS is not a GNU assembler and there is no link step, so the file that
``tools.build`` hands to ``as``/``ld`` cannot be loaded there. ``convert`` rewrites
a compiler listing into one file that RARS accepts and can run:

* ``.section .text`` becomes ``.text`` (RARS rejects a dotted section name),
  ``.bss`` becomes ``.data`` (RARS has no bss segment);
* directives RARS does not implement (``.option``, ``.type``, ``.size``,
  ``.balign``, ``.zero``) are dropped or translated to ``.align``/``.space``;
* the software arithmetic helpers from ``runtime/runtime.s`` are inlined;
* ``putchar``/``printint``/``printhex``/``exit`` become ecall shims;
* a ``main`` wrapper calls the compiled ``main`` and exits, because a RARS program
  starts at ``main`` with no caller to return to.

The conversion is deliberately a frontend-side text pass: the compiler keeps
emitting GNU assembly, and nothing in ``mycc.core`` gains file access.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime' / 'runtime.s'

# name -> (ecall number, argument register already holding the value)
SHIMS = {
    'putchar': 11,    # print char, a0
    'printint': 1,    # print int, a0
    'printhex': 34,   # print hex, a0
    'exit': 17,       # exit2, a0 = exit code
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


def convert(asm, runtime=True):
    """Return a single-file RARS listing equivalent to the GNU assembly `asm`."""
    body = asm
    if runtime and RUNTIME.exists():
        body += '\n' + RUNTIME.read_text(encoding='utf-8')
    # Keep the visible entry name for RARS while the compiled main keeps its body.
    body = re.sub(r'(?m)^\.globl\s+main\b', '.globl __mycc_main', body)
    body = re.sub(r'(?m)^main:', '__mycc_main:', body)
    lines = [line for line in (_rewrite(x) for x in body.splitlines()) if line is not None]
    text = '\n'.join(lines) + '\n'
    defined = set(LABEL.findall(text))
    used = set(CALL.findall(text))
    out = ENTRY + '\n' + text
    shims = [_shim(name, number) for name, number in SHIMS.items()
             if name in used and name not in defined]
    if shims:
        out += '\n# --- RARS syscall shims ---\n' + '\n\n'.join(shims) + '\n'
    return out
