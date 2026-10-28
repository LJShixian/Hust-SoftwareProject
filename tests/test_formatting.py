"""String literals and the compile-time lowering of `printf` / `scanf`.

There is no variadic ABI here. The format string must be a literal, so the front
end reads it, checks every conversion against the supplied arguments, and the code
generator emits one helper call per conversion. These tests pin the four things
that decision makes observable: where the literal bytes live, which helper each
conversion becomes, what a mismatched format reports, and that the whole chain
still produces the right text on a real RISC-V simulator.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from mycc import core
from mycc.rars import convert

ROOT = Path(__file__).resolve().parents[1]
RARS = Path(r'D:\Desktop\2026秋硬件综合训练课设资料发布包\RISC-V汇编工具与测试用例5.0'
            r'\RISC-V汇编工具与测试用例5.0\rars_f0c874c.jar')


def compile_source(text, profile='logisim'):
    from adapters.logisim import options
    return core.compile(core.SourceFile(text, 't.c'), core.load_profile(profile), options=options())


def listing_of(text):
    result = compile_source(text)
    assert result.success, [d.message for d in result.diagnostics]
    return convert(result.asm, profile=core.load_profile('logisim'), stack_top=1024)


def helper_calls(listing):
    """Calls made by user `main` only, so runtime helpers are not counted."""
    body = listing.split('__mycc_main:', 1)[-1].split('\n.Lreturn_', 1)[0]
    return re.findall(r'jal ra,(\w+)', body)


def test_literal_bytes_land_in_the_data_section():
    """A literal must be readable with `lw`, which on this kit means RAM, not ROM."""
    result = compile_source('int main(void){ printf("Ab\\n"); return 0; }')
    data = re.search(r'\.section \.data\n\.balign 4\n(\.Lstr_0):\n\.word ([0-9,]+)', result.asm)
    assert data, 'the literal is not in a .data run right after its label'
    assert data.group(2).split(',')[:4] == ['65', '98', '10', '0']


def test_identical_literals_share_one_word_array():
    listing = listing_of('int main(void){ printf("x\\n"); printf("x\\n"); return 0; }')
    assert listing.count('.Lstr_1') == 0, 'the repeated literal should reuse .Lstr_0'


def test_each_conversion_becomes_one_direct_helper_call():
    listing = listing_of('int main(void){ int n = 7; printf("%d/%x/%c/%s%%", n, n, n, "s"); return 0; }')
    calls = helper_calls(listing)
    assert calls == ['printint', 'printstr', 'printhex', 'printstr', 'putchar',
                     'printstr', 'printstr', 'printstr'], calls


def test_printf_never_calls_a_function_named_printf():
    """The call is lowered away, so nothing may depend on a variadic callee."""
    listing = listing_of('int main(void){ printf("%d\\n", 1); return 0; }')
    assert 'jal ra,printf' not in listing
    assert not re.search(r'(?m)^printf:', listing)


def test_scanf_conversions_become_pointer_helpers():
    listing = listing_of('int main(void){ int a; int b; scanf("%d", &a); scanf("%c", &b); return 0; }')
    calls = [c for c in helper_calls(listing) if c in ('readint', 'readchar')]
    assert calls == ['readint', 'readchar']


@pytest.mark.parametrize('source, message', [
    ('int main(void){ printf("%d"); return 0; }', 'needs more arguments'),
    ('int main(void){ printf("plain", 3); return 0; }', 'conversion(s) but 1 argument'),
    ('int main(void){ printf("%d", "text"); return 0; }', "expects an int argument"),
    ('int main(void){ int a; scanf("%d", a); return 0; }', 'expects an int pointer'),
    ('int main(void){ printf("%q", 1); return 0; }', "'%q' is not supported"),
    ('int main(void){ printf(5); return 0; }', 'requires a literal format string'),
    ('int main(void){ printf(); return 0; }', 'needs a format string'),
    ('int main(void){ printf("100%"); return 0; }', "ends with a lone '%'"),
])
def test_format_errors_are_reported_at_compile_time(source, message):
    result = compile_source(source)
    assert not result.success
    assert any(message in d.message for d in result.diagnostics), [d.message for d in result.diagnostics]


def test_string_literal_is_a_pointer_and_rejects_extra_characters():
    assert compile_source('int main(void){ int* p; p = "abc"; return *p; }').success
    bad = compile_source('int main(void){ int* p; p = "中"; return 0; }')
    assert not bad.success and any('below U+0100' in d.message for d in bad.diagnostics)


def test_bad_escape_and_unterminated_literal_are_diagnosed():
    escape = compile_source('int main(void){ printf("a\\qb"); return 0; }')
    assert any(d.code == 'E-LEX-INVALID-ESCAPE' for d in escape.diagnostics)
    unclosed = compile_source('int main(void){ printf("abc); return 0; }')
    assert any(d.code == 'E-LEX-UNCLOSED-STRING' for d in unclosed.diagnostics)


@pytest.mark.skipif(not (RARS.exists() and shutil.which('java')),
                    reason='needs the course RARS jar and a Java runtime')
def test_formatted_io_matches_expected_text_on_real_riscv():
    """End-to-end check with the console shim replaced by an array reader.

    RARS 1.5 builds a new InputStreamReader on every ReadChar, so the first call
    drains a redirected stream and the second sees EOF. Feeding characters from an
    array keeps `readint`/`readchar` and the scanf lowering under test.
    """
    program = ('int main(void){ int a; int b; scanf("%d %d", &a, &b);'
               ' printf("%d+%d=%d %x %c\\n", a, b, a + b, a + b, 65); return 0; }')
    result = compile_source(program)
    assert result.success
    listing = convert(result.asm, profile=core.load_profile('logisim'), stack_top=1024)
    shim = ('getchar:\n    la t0, __probe_input\n    la t1, __probe_index\n'
            '    lw t2, 0(t1)\n    add t0, t0, t2\n    lbu a0, 0(t0)\n'
            '    addi t2, t2, 1\n    sw t2, 0(t1)\n    jalr zero, 0(ra)\n')
    fed = re.sub(r'getchar:\naddi a7,zero,12\necall\njalr zero,0\(ra\)', shim, listing)
    assert 'la t0, __probe_input' in fed, 'the getchar shim was not found'
    fed += '.data\n__probe_input:\n.asciz "17 25"\n__probe_index:\n.word 0\n'
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'probe.asm'
        path.write_text(fed, encoding='utf-8')
        done = subprocess.run(['java', '-jar', str(RARS), 'mc', 'CompactDataAtZero',
                               'nc', 'me', str(path)],
                              capture_output=True, text=True, timeout=180)
    assert '17+25=42 0x0000002a A' in done.stdout, done.stdout + done.stderr
