"""The hardware-course Logisim target: reduced ISA, bounded RAM, loadable images.

The course CPU decodes 23 instructions (19 base plus sll/sb/xor/bltu), keeps code
in a 1024-word ROM and data in a 1024-byte RAM, and has no linker. These tests pin
the three things that used to make that combination fail: a runtime that ignored
the profile, an address materialised through an unreadable text-segment literal,
and an image written byte-per-token into a word-wide ROM.
"""
import re
from pathlib import Path
import pytest
from mycc import core
from mycc.encode import AssembleError, assemble, hex_image
from mycc.rars import convert, images

ROOT = Path(__file__).resolve().parents[1]


def compile_text(text, profile='logisim'):
    return core.compile(core.SourceFile(text, 't.c'), core.load_profile(profile))


def compile_target(text):
    """Compile with the Logisim adapter policy, i.e. bounded data addresses."""
    from adapters.logisim import options
    return core.compile(core.SourceFile(text, 't.c'), core.load_profile('logisim'), options=options())


def sections(listing):
    """Yield (section, line) for every instruction, so text/data placement is testable."""
    current = 'text'
    for line in listing.splitlines():
        text = line.split('#')[0].strip()
        if text in ('.text', '.data'):
            current = text[1:]
            continue
        if text:
            yield current, text


def test_logisim_preset_matches_the_course_instruction_set():
    """PF-08 is the design report's table 1.1 intersected with what mycc can emit."""
    expected = set('add addi and andi beq bltu bne jal jalr lw or ori sb sll slli '
                   'slt slti sltu srai srli sub sw xor xori'.split())
    profile = core.load_profile('logisim')
    assert profile.instructions == expected
    assert len(profile.instructions) == 24


def test_logisim_hardware_decodes_more_than_the_compiler_emits():
    """The CPU also has divu/remu/csrr*/uret; mycc never needs to generate them."""
    from tools.check_logisim import HARDWARE_ONLY
    profile = core.load_profile('logisim')
    assert not (HARDWARE_ONLY & profile.instructions)
    assert HARDWARE_ONLY == {'divu', 'remu', 'csrrw', 'csrrsi', 'csrrci', 'uret'}


def test_logisim_preset_keeps_the_required_baseline():
    assert core.MV_ISA <= core.load_profile('logisim').instructions


def test_reduced_profile_never_emits_an_instruction_the_machine_lacks():
    """The handwritten runtime uses srl/sra; the listing must be lowered for PF-08."""
    source = ('int main(void){ int a = 17; int b = 5; printint(a/b); printint(a%b);'
              ' printint(a>>b); return 0; }')
    listing = convert(compile_text(source).asm, profile=core.load_profile('logisim'))
    emitted = {text.split()[0] for section, text in sections(listing)
               if section == 'text' and not text.startswith('.') and not text.endswith(':')}
    outside = emitted - core.load_profile('logisim').instructions - {'ecall'}
    assert not outside, f'listing uses instructions the CPU cannot decode: {sorted(outside)}'
    assert 'sltu' in core.load_profile('logisim').instructions


def test_runtime_is_lowered_only_once_so_helper_labels_stay_unique():
    """Withholding `sb` forces the runtime through the fallback path."""
    source = 'int main(void){ printint(17/5); return 0; }'
    result = core.compile(core.SourceFile(source, 't.c'), core.load_profile('logisim'))
    listing = convert(result.asm, profile=core.load_profile('PF-01', disable=['sb']))
    labels = re.findall(r'(?m)^([A-Za-z_.$][\w.$]*):', listing)
    duplicates = {name for name in labels if labels.count(name) > 1}
    assert not duplicates, f'labels defined more than once: {sorted(duplicates)}'
    assert '__mv_sb' in labels, 'the withheld store should pull in its helper'


def test_global_addresses_use_bounded_relocations_not_a_rom_literal():
    """A Harvard ROM cannot be read by `lw`, so the PC-literal pool is unusable."""
    source = 'int data[3] = {1,2,3};\nint main(void){ printint(data[2]); return 0; }'
    listing = convert(compile_target(source).asm, profile=core.load_profile('logisim'))
    assert '%lo(data)' in listing
    assert 'lw a0,8(a0)' not in listing, 'address literals must not come from the text segment'


def test_entry_stub_loads_the_stack_pointer_when_asked():
    listing = convert(compile_text('int main(void){ return 0; }').asm,
                      profile=core.load_profile('logisim'), stack_top=1024)
    assert 'addi sp,zero,1024' in listing


def test_entry_stub_omits_the_stack_pointer_by_default():
    listing = convert(compile_text('int main(void){ return 0; }').asm, runtime=False)
    assert 'addi sp,zero,1024' not in listing


def test_stack_pointer_above_the_immediate_range_needs_lui():
    profile = core.load_profile('logisim')
    with pytest.raises(ValueError, match='needs lui'):
        convert(compile_text('int main(void){ return 0; }').asm, profile=profile,
                runtime=False, stack_top=0x7FFFEFFC)


def test_data_directives_leave_the_text_segment():
    """A switch jump table is emitted inline in .text, which RARS rejects."""
    source = '''
int calls;
int tick(int n){ calls = calls + 1; return n > 2 ? n - 1 : n + 1; }
int main(void){ int i; for (i = 0; i < 3; i = tick(i)) { if (i == 2) break; } printint(calls); return 0; }
'''
    listing = convert(compile_text(source).asm, profile=core.load_profile('logisim'))
    for section, text in sections(listing):
        if text.startswith('.word') or text.startswith('.space'):
            assert section == 'data', f'{text} still sits in the text segment'


def test_encoder_lays_text_and_data_in_separate_spaces():
    listing = ('.text\n.globl main\nmain:\naddi sp,zero,1024\njal ra,f\n'
               '.data\nk:\n.word 7\n.text\nf:\nlw a0,0(zero)\njalr zero,0(ra)\n')
    text_words, data_words, symbols = assemble(listing)
    assert symbols['main'] == 0 and symbols['f'] == 8 and symbols['k'] == 0
    assert len(text_words) == 4 and data_words == [7]


def test_encoder_reports_unknown_mnemonics_instead_of_guessing():
    with pytest.raises(AssembleError, match='unsupported mnemonic'):
        assemble('.text\nfrobnicate a0,a1\n')


def test_encoder_branch_offsets_are_relative_to_the_branch_itself():
    listing = '.text\nbeq a0,zero,skip\naddi a0,zero,1\nskip:\naddi a0,zero,2\n'
    words, _, _ = assemble(listing)
    offset = (((words[0] >> 31) & 1) << 12) | (((words[0] >> 25) & 0x3F) << 5) \
        | (((words[0] >> 8) & 0xF) << 1) | (((words[0] >> 7) & 1) << 11)
    if offset & 0x1000:
        offset -= 0x2000
    assert offset == 8


def test_hex_image_is_one_word_per_line():
    image = hex_image([0x00100293, 0x00000073])
    assert image == 'v2.0 raw\n00100293\n00000073\n'


def test_images_returns_a_rom_pair_for_a_program_with_globals(tmp_path):
    source = 'int table[2] = {4,9};\nint main(void){ printint(table[1]); return 0; }'
    listing, rom, ram = images(compile_target(source).asm, profile=core.load_profile('logisim'),
                               stack_top=1024)
    assert rom and all(0 <= word <= 0xFFFFFFFF for word in rom)
    assert ram == [4, 9]
    assert 'addi sp,zero,1024' in listing


def test_hardware_images_turn_outputs_into_display_checkpoints():
    """Every ecall pauses for `go`; a7=34 also shows a0. Characters just have no display."""
    source = 'int main(void){ printint(7); putchar(65); printhex(255); return 0; }'
    listing = convert(compile_target(source).asm, profile=core.load_profile('logisim'),
                      hardware_io=True)
    body = listing.split('# --- RARS syscall shims ---')[-1]
    putchar = body.split('putchar:')[1].split('.globl')[0]
    printint = body.split('printint:')[1].split('.globl')[0]
    printhex = body.split('printhex:')[1]
    assert 'ecall' not in putchar, 'a pause per separator char would bury the checkpoints'
    assert 'addi a7,zero,34' in printint and 'ecall' in printint
    assert 'addi a7,zero,34' in printhex and 'ecall' in printhex


def test_simulator_listing_keeps_real_syscalls_for_rars():
    source = 'int main(void){ printint(7); return 0; }'
    listing = convert(compile_target(source).asm, profile=core.load_profile('logisim'),
                      hardware_io=False)
    body = listing.split('# --- RARS syscall shims ---')[-1]
    assert 'addi a7,zero,1' in body


def test_logisim_target_rejects_a_profile_the_cpu_cannot_decode():
    from adapters.logisim import validate_profile
    with pytest.raises(core.ProfileError, match='does not decode'):
        validate_profile(core.load_profile('PF-07'))
    validate_profile(core.load_profile('logisim'))


def test_image_decode_recognises_the_course_encodings():
    from tools.check_logisim import decode
    assert decode(0x00100293) == 'addi'
    assert decode(0x00000073) == 'ecall'
    assert decode(0x00200073) == 'uret'
    assert decode(0x00100513) == 'addi'
    assert decode(0x02200893) == 'addi'
    assert decode(0x00000000) is None


def test_image_preflight_passes_for_every_example():
    from tools.check_logisim import check
    problems = check(quiet=True)
    assert problems == [], problems


def test_image_preflight_catches_an_instruction_the_cpu_lacks():
    """A profile with `mul` must be reported, so the gate cannot silently pass."""
    from tools.check_logisim import check
    source = ROOT / 'examples' / 'compiler' / 'muldiv.c'
    problems = check([source], profile=core.load_profile('PF-05'), quiet=True)
    assert problems and 'out-of-ISA' in problems[0]
    assert 'mul' in problems[0] or 'div' in problems[0]


def test_logisim_target_compiles_with_bounded_data_addresses():
    result = compile_target('int g = 5;\nint main(void){ return g; }')
    assert result.success
    assert '%lo(g)' in result.asm and 'slli' in result.asm


def test_classroom_demo_program_builds_a_loadable_pair():
    """The shipped demo must fit the kit and expose one checkpoint per printhex."""
    source = ROOT / 'examples' / 'logisim' / 'demo.c'
    result = compile_target(source.read_text(encoding='utf-8'))
    assert result.success
    listing, rom, ram = images(result.asm, profile=core.load_profile('logisim'), stack_top=1024)
    assert listing.count('jal ra,printhex') == 7, 'the demo should expose seven checkpoints'
    assert 0 < len(rom) <= 1024
    assert len(ram) * 4 <= 1024
