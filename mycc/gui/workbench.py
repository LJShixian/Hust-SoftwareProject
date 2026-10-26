"""Pure compiler workbench model, independent of boards and process runners."""
from dataclasses import dataclass, field
import json
from pathlib import Path
from .. import core


@dataclass
class WorkbenchState:
    text: str = 'int square(int x) { return x * x; }\n\nint main(void) {\n    return square(7);\n}\n'
    path: str = '<untitled>'
    baseline: str = 'PF-01'
    enable: list = field(default_factory=list)
    disable: list = field(default_factory=list)
    result: object = None
    last_asm: str = ''
    stale: bool = False
    legacy: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CompileRequest:
    src: core.SourceFile
    profile: core.ISAProfile
    options: core.CompileOptions


@dataclass(frozen=True)
class UiModel:
    asm_text: str
    diag_rows: list
    lowering_text: str
    status_line: str
    stale_flags: bool


def build_request(state):
    return CompileRequest(core.SourceFile(state.text,state.path),
                          core.load_profile(state.baseline,state.enable,state.disable),core.CompileOptions())


def apply_result(state,res):
    state.result=res
    if res.success: state.last_asm=res.asm
    state.stale=not res.success
    status='已取消' if res.cancelled else ('编译成功 · GNU 汇编' if res.success else '编译失败 · 汇编为上次成功结果')
    status+=f' · {sum(res.stages_ms.values()):.1f} ms · {len(res.asm.splitlines())} 行'
    return UiModel(state.last_asm,sorted(res.diagnostics,key=lambda d:(d.line,d.col)),
                   core.dump_lowering_report(res),status,state.stale)


def export_asm_diag_lowering(state):
    res=state.result
    if res is None: return state.last_asm,'',''
    diag=''.join(core.format_with_caret(d,res.source or core.SourceFile(state.text,state.path)) for d in res.diagnostics)
    md='| Operation | Selected lowering | Rejected |\n|---|---|---|\n'
    md+=''.join(f'| {op} | {reason} | {", ".join(rej)} |\n' for op,reason,rej in res.lowering)
    return state.last_asm,diag,md


def source_offset(text,line,col):
    lines=text.splitlines(keepends=True)
    if not lines: return 0
    index=max(0,min(line-1,len(lines)-1))
    return sum(len(x) for x in lines[:index])+min(max(0,col-1),len(lines[index].rstrip('\r\n')))


def settings_path():
    return Path.home()/'.config'/'mycc'/'gui.json'


def default_settings():
    return {'baseline':'PF-01','enable':[],'disable':[],'legacy':{}}


def load_settings(path=None):
    try:
        data=json.loads((path or settings_path()).read_text(encoding='utf-8'))
        if not isinstance(data,dict) or set(data)-{'schema_version','baseline','enable','disable','legacy','board'}:
            raise ValueError('unknown settings fields')
        if data.get('schema_version',2)!=2: raise ValueError('unsupported settings version')
        core.load_profile(data['baseline'],data.get('enable',[]),data.get('disable',[]))
        legacy=data.get('legacy',{})
        if not isinstance(legacy,dict): raise ValueError('legacy must be an object')
        message=''
        if 'board' in data:
            legacy={**legacy,'board':data['board']}
            message='旧板卡地址设置已保存在 legacy 中；当前工作台仅编译汇编'
        return {'baseline':data['baseline'],'enable':data.get('enable',[]),
                'disable':data.get('disable',[]),'legacy':legacy},message
    except FileNotFoundError: return default_settings(),''
    except (OSError,ValueError,KeyError,TypeError,core.ProfileError):
        return default_settings(),'设置损坏，已恢复编译器默认值'


def save_settings(state,path=None):
    try:
        target=path or settings_path(); target.parent.mkdir(parents=True,exist_ok=True)
        data={'schema_version':2,'baseline':state.baseline,'enable':state.enable,'disable':state.disable,'legacy':state.legacy}
        target.write_text(json.dumps(data,indent=2),encoding='utf-8')
        return ''
    except OSError as exc: return f'无法保存设置: {exc}'
