from mycc import core
from mycc.gui.workbench import (WorkbenchState,build_request,apply_result,export_asm_diag_lowering,
    source_offset,load_settings,save_settings)


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
    assert load_settings(path)[0]=={'baseline':'PF-02','enable':['mul'],'disable':['div'],'legacy':{}}
    path.write_text('{invalid')
    assert load_settings(path)[1]
    path.write_text('{"unknown":true}')
    assert load_settings(path)[1]


def test_offsets_exports():
    assert source_offset('a\n\t汉字\n',2,3)==4
    assert source_offset('',1,1)==0
    state=WorkbenchState(path='path with spaces.c',enable=['div'],disable=['lui'])
    assert export_asm_diag_lowering(state)==('','','')


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
