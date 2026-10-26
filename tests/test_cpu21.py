import json
from pathlib import Path
import subprocess
import pytest
from mycc import core,cli
from tools.build import ROOT,build,tool,export_rom,main


def cpu_compile(text,disabled=()):
    return core.compile(core.SourceFile(text),core.load_profile('cpu21',disable=disabled),options=core.CompileOptions(target='cpu21'))


def test_harvard_initializers_and_no_literal_pool():
    text='int a=7;int b[3]={0x12345678,-2,3};int main(){return a+b[1];}'
    for disabled in [[],['lui'],['lui','vshift']]:
        res=cpu_compile(text,disabled)
        assert res.success
        assert '.section .data' not in res.asm and '.word ' not in res.asm
        assert '__mycc_init_globals:' in res.asm
        assert 'sw a0,0(t0)' in res.asm
        if 'lui' in disabled:
            assert '\nlui ' not in res.asm
            assert 'addi a0,zero,%lo(a)' in res.asm
        assert 'jal zero,__mycc_stack_overflow' in res.asm


@pytest.mark.parametrize('profile',['PF-04','PF-05','PF-06','PF-07'])
def test_hardware_capabilities_checked_before_source(profile):
    with pytest.raises(core.ProfileError) as exc:
        core.compile(core.SourceFile('invalid @'),core.load_profile(profile),options=core.CompileOptions(target='cpu21'))
    assert exc.value.code=='E-TARGET-ISA' and exc.value.exit_code==64


def test_generic_target_preserves_hardware_division():
    result=core.compile(core.SourceFile('int main(){return 17/5;}'),core.load_profile('PF-05'))
    assert result.success and 'div a0,t0,a0' in result.asm
    default_cpu=core.compile(core.SourceFile('int main(){return 3*7;}'),options=core.CompileOptions(target='cpu21'))
    assert default_cpu.success and 'mul a0,t0,a0' in default_cpu.asm
    with pytest.raises(core.ProfileError): core.check_target(core.load_profile(),'typo')
    assert not cpu_compile('int __mycc_init_globals;int main(){return 0;}').success


@pytest.mark.parametrize('patch',[
    {'led':'bad'},{'led':3},{'led':0},{'led':0x8000},{'vga_base':0x7ffc},
    {'led':0x1004},{'led':0x2004},
])
def test_cpu21_config_rejects_invalid_addresses(patch):
    with pytest.raises(ValueError): core.CPU21Board.from_mapping(core.CPU21Board().as_dict()|patch)


def test_word_rom_export(tmp_path):
    out=tmp_path/'firmware'
    export_rom(bytes.fromhex('730f400013000000'),out)
    words=out.with_suffix('.hex').read_text().splitlines()
    assert len(words)==8192 and words[0]=='00400f73' and words[1]=='00000013'
    assert words[-1]=='00000013'
    assert "rom[0] = 32'h00400f73;" in out.with_suffix('.vh').read_text()
    with pytest.raises(RuntimeError): export_rom(b'\0'*32769,out)


def test_build_cpu21_uses_production_startup_and_manifest(tmp_path):
    try: tool('as')
    except RuntimeError: pytest.skip('GNU RISC-V tools absent')
    elf=build(ROOT/'bench/cpu21_selftest.c',output=tmp_path/'selftest')
    symbols=subprocess.check_output([tool('nm'),str(elf)],text=True)
    assert any(line.split()[0]=='00001000' and line.split()[-1]=='__stack_top' for line in symbols.splitlines())
    assert '__mycc_init_globals' in symbols
    manifest=json.loads(elf.with_suffix('.manifest.json').read_text())
    assert manifest['target']=='cpu21' and manifest['rom_word_bits']==32
    assert 'div' not in manifest['instructions'] and 'rem' not in manifest['instructions']
    assert elf.with_suffix('.hex').read_text().splitlines()[0]=='0040f073'


def test_build_rejects_generic_assembly_and_bss_overflow(tmp_path):
    try: tool('as')
    except RuntimeError: pytest.skip('GNU RISC-V tools absent')
    asm=tmp_path/'generic.s'
    asm.write_text(core.compile(core.SourceFile('int main(){return 0;}')).asm)
    with pytest.raises(RuntimeError,match='recompile'): build(asm,output=tmp_path/'wrong')
    src=tmp_path/'large.c'; src.write_text('int large[600];int main(){return 0;}')
    with pytest.raises(subprocess.CalledProcessError): build(src,output=tmp_path/'overflow')


def test_cli_defaults_and_explicit_generic(tmp_path,capsys):
    src=tmp_path/'program.c'; src.write_text('int main(){return 17/5;}')
    asm=tmp_path/'program.s'
    assert cli.main([str(src),'-o',str(asm)])==0
    assert '# mycc-target: cpu21' in asm.read_text()
    assert cli.main([str(src),'--profile','PF-05','-o',str(asm)])==64
    assert cli.main([str(src),'--profile','PF-05','--target','generic','-o',str(asm)])==0
    assert 'div a0,t0,a0' in asm.read_text()
    assert main([str(src),'--uart-tx','0x1000'])==1
    assert 'no UART' in capsys.readouterr().err


def test_cpu21_board_file_roundtrip(tmp_path):
    try: tool('as')
    except RuntimeError: pytest.skip('GNU RISC-V tools absent')
    config=tmp_path/'board.json'; config.write_text(json.dumps(core.CPU21Board().as_dict()))
    out=tmp_path/'board'
    assert main([str(ROOT/'bench/hello.c'),'--board-file',str(config),'-o',str(out)])==0
    assert out.with_suffix('.hex').exists()


def test_rtl_verifier_refuses_outputs_inside_hardware():
    from tools.verify_cpu21 import verify
    root=ROOT/'build/fake-hardware'
    with pytest.raises(ValueError): verify(root,root/'output')


def test_cpu21_reference_assets_match_target():
    for name in ('cpu21.json','hw_caps.json'):
        data=json.loads((ROOT/'isa'/name).read_text(encoding='utf-8'))
        assert core.load_profile(data=data).instructions==core.CPU21_INSTRUCTIONS
    board=json.loads((ROOT/'isa/cpu21.board.json').read_text())
    assert core.CPU21Board.from_mapping(board)==core.CPU21Board()
