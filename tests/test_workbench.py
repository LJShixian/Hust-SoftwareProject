from mycc import core
from mycc.gui import workbench
from mycc.gui.workbench import (WorkbenchState,build_request,apply_result,export_asm_diag_lowering,
    source_offset,load_settings,save_settings,normalize_capabilities,command_text,artifacts)


def test_cli_gui_shared_results():
    state=WorkbenchState()
    req=build_request(state); res=core.compile(req.src,req.profile,options=req.options)
    ui=apply_result(state,res)
    assert ui.asm_text==res.asm
    assert ui.lowering_text==core.dump_lowering_report(res)
    asm,diag,md=export_asm_diag_lowering(state)
    assert asm==res.asm and not diag and 'MUL' in md
    old=state.last_asm
    state.text='int main(){return missing;}'
    req=build_request(state); res=core.compile(req.src,req.profile,options=req.options)
    ui=apply_result(state,res)
    assert ui.asm_text==old and ui.stale_flags
    assert export_asm_diag_lowering(state)[1]==''.join(core.format_with_caret(d,req.src) for d in res.diagnostics)


def test_settings_roundtrip_and_recovery(tmp_path):
    path=tmp_path/'settings.json'
    assert load_settings(path)[0]['baseline']=='PF-01'
    state=WorkbenchState(baseline='PF-02',enable=['mul'],disable=['div'])
    assert not save_settings(state,path)
    settings=load_settings(path)[0]
    assert settings['baseline']=='PF-02' and settings['enable']==['mul'] and settings['disable']==['div']
    assert settings['target']=='generic' and settings['theme']=='system'
    assert settings['dumps']['tokens'] is True and settings['write_output'] is False
    path.write_text('{invalid')
    assert load_settings(path)[1]
    path.write_text('{"unknown":true}')
    assert load_settings(path)[1]


def test_offsets_exports():
    assert source_offset('a\n\t汉字\n',2,3)==4
    assert source_offset('',1,1)==0
    state=WorkbenchState(path='path with spaces.c',enable=['div'],disable=['lui'])
    assert export_asm_diag_lowering(state)==('','','')


def test_capability_differences_are_relative_to_the_preset():
    """Only real differences from the preset may be persisted.

    Regression: every unchecked box used to be written into `disable`, including
    groups the preset never contained. PF-01 then reopened as 22 instructions
    instead of 26 while the combo still said PF-01.
    """
    assert normalize_capabilities('PF-01',[],['mul','divrem','xor','cmpbr','byteload','auipc','lui','vshift'])==([],['lui','vshift'])
    assert normalize_capabilities('PF-01',['mul','lui'],[])==(['mul'],[])
    assert normalize_capabilities('PF-05',['mul'],[])==([],[])
    assert normalize_capabilities('PF-05',['mul'],['mul'])==([],['mul'])


def test_zoom_shortcuts_cover_plus_equal_and_minus(tmp_path,monkeypatch):
    """Ctrl+'+' arrives as Ctrl+Shift+'=' on a US layout; all three chords must zoom."""
    import os
    os.environ['QT_QPA_PLATFORM']='offscreen'
    import pytest
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from mycc.gui.views import MainWindow
    from mycc.gui import workbench
    monkeypatch.setattr(workbench,'settings_path',lambda:tmp_path/'gui.json')
    app=QApplication.instance() or QApplication([])
    window=MainWindow(); window.show(); QTest.qWait(20)
    def height(): return window.editor.fontMetrics().height()
    before=height()
    QTest.keyClick(window.editor,Qt.Key_Plus,Qt.ControlModifier|Qt.ShiftModifier); QTest.qWait(20)
    assert height()>before
    before=height()
    QTest.keyClick(window.editor,Qt.Key_Equal,Qt.ControlModifier); QTest.qWait(20)
    assert height()>before
    before=height()
    QTest.keyClick(window.editor,Qt.Key_Minus,Qt.ControlModifier); QTest.qWait(20)
    assert height()<before
    window.close()


def test_offscreen_window(tmp_path,monkeypatch):
    import os
    os.environ['QT_QPA_PLATFORM']='offscreen'
    import pytest
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from mycc.gui.views import MainWindow
    from mycc.gui import workbench
    monkeypatch.setattr(workbench,'settings_path',lambda:tmp_path/'gui.json')
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    assert not hasattr(window,'board_fields')
    assert not hasattr(window,'process')
    window.profile.setCurrentIndex(4)
    assert window.state.baseline=='PF-05'
    assert window.checkboxes['divrem'].isEnabled()
    assert window.checkboxes['byteload'].isEnabled()
    window.editor.setPlainText('int main(){return 42;}')
    window.editor.document().setModified(False)
    window.start_compile()
    import time
    deadline=time.monotonic()+5
    while window.worker and time.monotonic()<deadline:
        app.processEvents(); time.sleep(0.01)
    assert window.worker is None and window.state.result.success
    assert 'addi a0,zero,42' in window.outputs['汇编'].toPlainText()
    window.close()
    second=MainWindow()
    assert second.state.baseline=='PF-05'
    second.close()


def test_command_text_exposes_cli_switches():
    state=WorkbenchState(
        baseline='PF-01',target='logisim',output='out.asm',write_output=True,rars=True,
        logisim=True,stack_top='1024',isa_file='isa.json',enable=['mul'],
        disable=['lui','vshift'],stats=True)
    state.dumps={key:False for key in workbench.DUMP_KEYS}
    state.dumps['isa']=True
    state.dumps['isa_whitelist']=True
    text=command_text(state)
    for token in ('--target logisim','--rars','--logisim','--stack-top 1024',
                  '--isa-file isa.json','--profile PF-01','--enable mul','--no-lui',
                  '--no-vshift','--dump-isa','--dump-isa-whitelist','--stats','-o out.asm'):
        assert token in text, token
    assert '--dump-tokens' not in text
    assert '--disable lui' not in text and '--disable vshift' not in text


def test_gui_artifacts_write_asm_rars_and_logisim(tmp_path):
    def compile_state(state):
        request=build_request(state)
        result=core.compile(request.src,request.profile,options=request.options)
        assert result.success, [d.message for d in result.diagnostics]
        return request,result
    src='int main(void){ return 42; }'
    asm_state=WorkbenchState(text=src,output=str(tmp_path/'x.s'),write_output=True)
    request,result=compile_state(asm_state)
    paths=artifacts(asm_state,request,result)
    assert paths==[str(tmp_path/'x.s')]
    assert (tmp_path/'x.s').read_text(encoding='utf-8')==result.asm

    rars_state=WorkbenchState(text=src,output=str(tmp_path/'y.s'),write_output=True,rars=True)
    request,result=compile_state(rars_state)
    assert artifacts(rars_state,request,result)
    assert '__mycc_main' in (tmp_path/'y.s').read_text(encoding='utf-8')

    logisim_state=WorkbenchState(text=src,baseline='PF-08',target='logisim',
                                 output=str(tmp_path/'z.asm'),write_output=True,
                                 rars=True,logisim=True,stack_top='1024')
    request,result=compile_state(logisim_state)
    paths=artifacts(logisim_state,request,result)
    assert str(tmp_path/'z.asm') in paths and str(tmp_path/'z.rom.hex') in paths
    assert (tmp_path/'z.rom.hex').read_text(encoding='utf-8').startswith('v2.0 raw\n')

    # A directory (including one that does not exist yet) receives a default
    # file name derived from the source name, rather than being replaced.
    directory_state=WorkbenchState(text=src,path='demo.c',output=str(tmp_path/'outdir'),write_output=True)
    request,result=compile_state(directory_state)
    paths=artifacts(directory_state,request,result)
    assert paths==[str(tmp_path/'outdir'/'demo.s')]
    assert (tmp_path/'outdir'/'demo.s').read_text(encoding='utf-8')==result.asm
    assert workbench.output_file(directory_state)==tmp_path/'outdir'/'demo.s'
    assert '-o' in command_text(directory_state)
    assert str(tmp_path/'outdir'/'demo.s') in command_text(directory_state)


def test_theme_and_target_settings_roundtrip(tmp_path):
    path=tmp_path/'settings.json'
    state=WorkbenchState(baseline='PF-08',target='logisim',output='build/x.asm',
                         write_output=True,rars=True,logisim=True,stack_top='1024',
                         stats=True,theme='dark')
    state.dumps['isa']=True
    assert not save_settings(state,path)
    loaded=load_settings(path)[0]
    assert loaded['target']=='logisim' and loaded['theme']=='dark'
    assert loaded['write_output'] is True and loaded['stack_top']=='1024'
    assert loaded['dumps']['isa'] is True


def test_gui_target_and_theme_controls(tmp_path,monkeypatch):
    import os
    os.environ['QT_QPA_PLATFORM']='offscreen'
    import pytest
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from mycc.gui.views import MainWindow
    from mycc.gui import workbench
    monkeypatch.setattr(workbench,'settings_path',lambda:tmp_path/'gui.json')
    app=QApplication.instance() or QApplication([])
    window=MainWindow(); window.show()
    window.target_combo.setCurrentIndex(window.target_combo.findData('logisim'))
    assert window.state.target=='logisim' and window.state.baseline=='PF-08'
    assert window.rars_check.isChecked() and window.logisim_check.isChecked()
    assert not window.profile.isEnabled()
    window.apply_theme('dark')
    assert window.state.theme=='dark'
    assert '#0f1115' in app.styleSheet()
    window.theme_combo.setCurrentIndex(window.theme_combo.findData('light'))
    assert window.state.theme=='light'
    window.close()


def test_gui_ctrl_shift_f_formats_document(tmp_path,monkeypatch):
    import os
    os.environ['QT_QPA_PLATFORM']='offscreen'
    import pytest
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from mycc.gui.views import MainWindow
    from mycc.gui import workbench
    monkeypatch.setattr(workbench,'settings_path',lambda:tmp_path/'gui.json')
    app=QApplication.instance() or QApplication([])
    window=MainWindow(); window.show()
    window.editor.setPlainText('int main(){\nif(1){\nreturn 0;\n}\n}\n')
    window.editor.setFocus()
    QTest.qWait(20)
    QTest.keyClick(window.editor,Qt.Key_F,Qt.ControlModifier|Qt.ShiftModifier)
    QTest.qWait(20)
    assert window.editor.toPlainText()==(
        'int main() {\n    if (1) {\n        return 0;\n    }\n}\n')
    window.editor.document().setModified(False)
    window.close()


def test_gui_folder_browser_sets_output_directory(tmp_path,monkeypatch):
    import os
    os.environ['QT_QPA_PLATFORM']='offscreen'
    import pytest
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication, QFileDialog
    from mycc.gui.views import MainWindow
    from mycc.gui import workbench
    monkeypatch.setattr(workbench,'settings_path',lambda:tmp_path/'gui.json')
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args,**kwargs:str(tmp_path))
    app=QApplication.instance() or QApplication([])
    window=MainWindow(); window.show()
    window.browse_output_dir()
    assert window.state.output==str(tmp_path)
    assert window.output_edit.text()==str(tmp_path)
    window.close()


def test_gui_ctrl_s_saves_even_with_completion_popup(tmp_path,monkeypatch):
    import os
    os.environ['QT_QPA_PLATFORM']='offscreen'
    import pytest
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from mycc.gui.views import MainWindow
    from mycc.gui import workbench
    monkeypatch.setattr(workbench,'settings_path',lambda:tmp_path/'gui.json')
    app=QApplication.instance() or QApplication([])
    source=tmp_path/'demo.c'; source.write_text('old',encoding='utf-8')
    window=MainWindow(); window.show(); window.activateWindow()
    window.state.path=str(source)
    window.editor.setPlainText('int alpha; int main(void){ al')
    cursor=window.editor.textCursor(); cursor.movePosition(QTextCursor.End); window.editor.setTextCursor(cursor)
    window.editor.setFocus(); QTest.qWait(20)
    QTest.keyClick(window.editor,Qt.Key_P); QTest.qWait(100)
    assert window.editor.completer.popup().isVisible()
    QTest.keyClick(window.editor,Qt.Key_S,Qt.ControlModifier); QTest.qWait(50)
    assert source.read_text(encoding='utf-8')=='int alpha; int main(void){ alp'
    assert not window.editor.document().isModified()
    window.close()
