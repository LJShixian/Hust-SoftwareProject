import json
import pytest
from mycc import cli,core


def test_cli_direct_success_and_dumps(tmp_path,capsys):
    src=tmp_path/'good.c'; dest=tmp_path/'good.s'; src.write_text('int main(){return 3*7;}')
    assert cli.main([str(src),'-o',str(dest),'--dump-tokens','--dump-ast','--dump-ir','--dump-lowering-report','--stats'])==0
    out=capsys.readouterr(); assert 'MUL' in out.out and 'lex\t' in out.err
    assert dest.read_text()==core.compile(core.SourceFile(src.read_text(),str(src))).asm
    assert cli.main(['--dump-isa','--dump-isa-whitelist','--no-lui','--no-vshift'])==0
    assert 'base' in capsys.readouterr().out
    assert cli.main(['--doctor'])==0


def test_cli_direct_errors(tmp_path,capsys):
    src=tmp_path/'bad.c'; src.write_text('int main(){return x;}')
    assert cli.main([str(src)])==1
    assert cli.main(['--dump-isa','--disable','jalr'])==64
    assert cli.main([str(tmp_path/'missing.c')])==65
    src.write_bytes(b'\xff'); assert cli.main([str(src)])==65
    src.write_text(' '*131073); assert cli.main([str(src)])==65
    src.write_text('int main(){return 0;}')
    assert cli.main([str(src),'-o',str(tmp_path/'absent'/'out.s')])==70
    assert cli.main(['--isa-file',str(tmp_path/'absent.json'),'--dump-isa'])==65
    with pytest.raises(SystemExit) as exc: cli.run(['file.txt'])
    assert exc.value.code==64


def test_cli_profile_json_and_atomic_cleanup(tmp_path,capsys,monkeypatch):
    profile=tmp_path/'board.json'
    profile.write_text(json.dumps({'name':'board','schema_version':1,'description':'test','instructions':list(core.load_profile().instructions)}))
    assert cli.main(['--isa-file',str(profile),'--dump-isa'])==0
    assert 'board' in capsys.readouterr().out
    target=tmp_path/'out.s'; target.write_text('original')
    def broken(*_): raise OSError('simulated rename failure')
    monkeypatch.setattr(cli.os,'replace',broken)
    with pytest.raises(OSError): cli.atomic_write(target,'new')
    assert target.read_text()=='original' and not list(tmp_path.glob('.mycc-tmp-*'))


def test_cli_internal_error_and_interrupt(monkeypatch,capsys):
    def broken(*_): raise RuntimeError('injected')
    monkeypatch.setattr(cli,'run',broken)
    assert cli.main([])==2 and 'internal compiler error' in capsys.readouterr().err
    def interrupt(*_): raise KeyboardInterrupt()
    monkeypatch.setattr(cli,'run',interrupt)
    assert cli.main([])==130


def test_custom_profile_validation_and_suggestions():
    good={'name':'board','schema_version':1,'instructions':sorted(core.load_profile().instructions)}
    a=core.load_profile(data=good)
    assert a.instructions==core.load_profile().instructions
    for patch in [{'name':'bad name'},{'name':'base'},{'description':'x'*201},{'instructions':'bad'}, {'instructions':[]}]:
        with pytest.raises(core.ProfileError): core.load_profile(data=good|patch)
    with pytest.raises(core.ProfileError): core.load_profile(data=[])
    with pytest.raises(core.ProfileError): core.load_profile(enable=['mull'])
    assert 'alternatives' in core.dump_isa(a)


def test_gui_missing_dependency_fallback(monkeypatch,capsys):
    import builtins
    from mycc.gui.app import launch
    original=builtins.__import__
    def blocked(name,*args,**kwargs):
        if name.startswith('PySide6'): raise ImportError('injected dependency absence')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',blocked)
    assert launch()==64
    assert 'PySide6' in capsys.readouterr().err
