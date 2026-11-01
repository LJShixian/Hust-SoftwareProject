"""Regression tests for the review findings on mycc 2.0."""
from pathlib import Path

from mycc import core, cli
from mycc.encode import assemble, validate_image
from mycc.rars import convert, images


def compile_text(text, profile='PF-01', **kwargs):
    return core.compile(core.SourceFile(text, 't.c'), core.load_profile(profile, **kwargs))


def test_sizeof_array_in_array_bound_uses_the_real_element_size():
    result = compile_text('int b[3]; int a[sizeof(b)]; int main(void){ return sizeof(a); }')
    assert result.success, [d.message for d in result.diagnostics]
    assert '.zero 48' in result.asm, 'int a[sizeof(int[3])] must reserve 12 ints'


def test_pointer_array_is_rejected_instead_of_degrading_to_int_array():
    result = compile_text('int x; int *p[2]; int main(void){ p[0] = 0; return 0; }')
    assert not result.success
    assert result.diagnostics[0].code == 'E-UNSUPPORTED-CONSTRUCT'


def test_scanf_literal_text_is_rejected_not_printed():
    result = compile_text('int main(void){ int x; scanf("X%d", &x); return 0; }')
    assert not result.success
    assert result.diagnostics[0].code == 'E-SEMA-FORMAT'


def test_scanf_whitespace_does_not_emit_print_calls():
    result = compile_text('int main(void){ int a; int b; scanf("%d %d", &a, &b); return 0; }')
    assert result.success
    assert 'jal ra,printstr' not in result.asm


def test_rars_without_lui_and_a_global_is_rejected():
    profile = core.load_profile(disable=['lui'])
    result = core.compile(core.SourceFile('int a=7; int b=9; int main(void){ return b; }', 't.c'), profile)
    assert result.success
    try:
        convert(result.asm, profile=profile, stack_top=512)
    except ValueError as exc:
        assert 'lui' in str(exc)
    else:
        raise AssertionError('the PC-literal fallback must not reach a RARS listing')


def test_reduced_profile_merged_listing_assembles_once():
    profile = core.load_profile(disable=['lui', 'slli'])
    result = core.compile(core.SourceFile('int main(void){ return 100000; }', 't.c'), profile)
    assert result.success
    listing = convert(result.asm, profile=profile, stack_top=512)
    words, data, _ = assemble(listing)
    assert words and not data


def test_images_defaults_to_a_stack_pointer_for_the_classroom_target():
    profile = core.load_profile('logisim')
    result = core.compile(core.SourceFile('int main(void){ return 0; }', 't.c'), profile)
    text, rom, ram = images(result.asm, profile=profile)
    assert 'addi sp,zero,1024' in text
    assert rom


def test_image_validation_rejects_capacity_overruns():
    profile = core.load_profile('logisim')
    rom_problems = validate_image([0x00000013] * 1025, [], profile)
    assert any('ROM' in problem for problem in rom_problems)
    ram_problems = validate_image([0x00000013], [0] * 257, profile)
    assert any('RAM' in problem for problem in ram_problems)


def test_cli_requires_the_logisim_target_for_images(tmp_path):
    code = cli.run(['examples/compiler/hello.c', '--logisim', '-o', str(tmp_path / 'x.asm')])
    assert code == 64


def test_cli_invalid_stack_top_is_a_usage_error(tmp_path):
    code = cli.run(['examples/compiler/hello.c', '--rars', '--stack-top', '0x100000000',
                    '-o', str(tmp_path / 'x.asm')])
    assert code == 64


def test_recursive_main_calls_the_compiled_body():
    result = compile_text('int main(void){ if (0) return main(); return 0; }')
    text = convert(result.asm)
    assert 'jal ra,main' not in text
    assert 'jal ra,__mycc_main' in text


def test_normalize_accepts_single_instruction_names():
    from mycc.gui.workbench import normalize_capabilities
    assert normalize_capabilities('PF-01', ['sll'], []) == ([], [])
