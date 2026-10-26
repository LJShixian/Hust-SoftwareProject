"""The three compiler demonstrations and boundaries from CR-SCOPE-001."""
import json
import subprocess
import sys
import pytest
from mycc import core,cli
from mycc.gui.workbench import WorkbenchState,build_request,load_settings,save_settings
from tools.build import ROOT,tool


def test_default_compilation_needs_no_board_adapter_or_toolchain(tmp_path):
    # Fresh process: normal CLI compilation must not even import adapters.
    src=tmp_path/'program.c'; src.write_text('int main(){return 6*7;}')
    out=tmp_path/'program.s'
    script="from mycc.cli import main; import sys; code=main(sys.argv[1:]); assert 'adapters' not in sys.modules; raise SystemExit(code)"
    p=subprocess.run([sys.executable,'-c',script,str(src),'-o',str(out)],capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    asm=out.read_text()
    assert '# mycc-target: generic' in asm and '__mycc_init_globals' not in asm
    assert '__mycc_stack_overflow' not in asm


def test_sc_core_01_demo_generates_real_gnu_object(tmp_path):
    source=core.SourceFile((ROOT/'bench/compiler_demo.c').read_text(),'compiler_demo.c')
    result=core.compile(source)
    assert result.success and 'jal ra,__mulsi3' in result.asm
    try: assembler=tool('as')
    except RuntimeError: pytest.skip('GNU assembler absent; generation checked, object not checked')
    asm=tmp_path/'demo.s'; asm.write_text(result.asm)
    subprocess.run([assembler,'-march=rv32i','-mabi=ilp32','-mno-relax',str(asm),'-o',str(tmp_path/'demo.o')],check=True)
    assert (tmp_path/'demo.o').stat().st_size>0


def test_sc_core_02_isa_changes_lowering_without_changing_language():
    src=core.SourceFile('int square(int x){return x*x;}int main(){return square(7);}')
    software=core.compile(src,core.load_profile())
    hardware=core.compile(src,core.load_profile(enable=['mul']))
    assert software.success and hardware.success
    assert '__mulsi3' in software.asm and 'mul a0,t0,a0' in hardware.asm
    assert 'missing mul' in core.dump_lowering_report(software)
    assert 'hardware multiplication' in core.dump_lowering_report(hardware)
    assert software.ast_text==hardware.ast_text


def test_sc_core_03_diagnostics_and_output_preservation(tmp_path,capsys):
    src=tmp_path/'bad.c'; out=tmp_path/'previous.s'; out.write_text('previous successful output')
    for text in ['int main(){return 1 }','int main(){return unknown;}']:
        src.write_text(text)
        assert cli.main([str(src),'-o',str(out)])==1
        assert 'error:' in capsys.readouterr().err
        assert out.read_text()=='previous successful output'
    assert cli.main(['--dump-isa','--enable','mull'])==65
    assert 'suggestion' in capsys.readouterr().err


def test_all_isa_choices_available_without_a_board_constraint():
    for name in core.PRESETS:
        state=WorkbenchState(baseline=name)
        req=build_request(state)
        assert req.options.policy.name=='generic'
        result=core.compile(req.src,req.profile,options=req.options)
        assert result.success
        assert '__mycc_stack_overflow' not in result.asm
    result=core.compile(core.SourceFile('int main(){vga_cell(0,16,7);return 0;}'))
    assert not result.success and result.diagnostics[0].code=='E-SEMA-UNDECLARED-ID'


def test_legacy_board_settings_are_preserved_but_not_applied(tmp_path):
    path=tmp_path/'gui.json'
    board={'led':'0x1010','custom':'old data'}
    path.write_text(json.dumps({'baseline':'cpu21','enable':[],'disable':[],'board':board}))
    data,message=load_settings(path)
    assert data['legacy']['board']==board and message
    state=WorkbenchState(baseline=data['baseline'],legacy=data['legacy'])
    assert build_request(state).options.policy.name=='generic'
    assert not save_settings(state,path)
    saved=json.loads(path.read_text())
    assert saved['schema_version']==2 and saved['legacy']['board']==board
    assert 'board' not in saved
    path.write_text(json.dumps({'schema_version':999,'baseline':'PF-01'}))
    assert load_settings(path)[1]
    path.write_text(json.dumps({'baseline':'PF-01','legacy':[]}))
    assert load_settings(path)[1]


def test_codegen_policy_is_board_neutral_and_requires_explicit_injection():
    policy=core.CodegenPolicy(name='harvard_example',globals_in_bss=True,initializer='__mycc_example_init',data_address_bits=12)
    options=core.CompileOptions(target='harvard_example',policy=policy)
    result=core.compile(core.SourceFile('int value=7;int main(){return value;}'),options=options)
    assert result.success and '__mycc_example_init:' in result.asm
    assert '.section .data' not in result.asm
    with pytest.raises(core.ProfileError):
        core.compile(core.SourceFile('int main(){return 0;}'),options=core.CompileOptions(target='missing_adapter'))
    for data in [dict(data_address_bits=13),dict(globals_in_bss=True),dict(stack_guard_symbol='end'),dict(stack_guard_margin=2048)]:
        with pytest.raises(ValueError): core.CodegenPolicy(**data)
