"""Pure Python workbench model shared by tests and the Qt view."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from .. import core


@dataclass
class WorkbenchState:
    text: str = 'int main(void) {\n    printint(6 * 7);\n    return 0;\n}\n'
    path: str = '<untitled>'
    baseline: str = 'PF-01'
    enable: list = field(default_factory=list)
    disable: list = field(default_factory=list)
    result: object = None
    last_asm: str = ''
    stale: bool = False
    board: dict = field(default_factory=lambda:dict(uart_tx='0x10000000',vga_base='0x20000000',exit_status='0x10000004'))


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
    status='已取消' if res.cancelled else ('编译成功' if res.success else '编译失败 · 汇编为上次成功结果')
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


def load_settings(path=None):
    try:
        data=json.loads((path or settings_path()).read_text(encoding='utf-8'))
        if not isinstance(data,dict) or set(data)-{'baseline','enable','disable','board'}: raise ValueError('unknown settings fields')
        core.load_profile(data['baseline'],data.get('enable',[]),data.get('disable',[]))
        if 'board' in data: board_arguments(data['board'])
        return data,''
    except FileNotFoundError: return {'baseline':'PF-01','enable':[],'disable':[]},''
    except (OSError,ValueError,KeyError,TypeError,core.ProfileError):
        return {'baseline':'PF-01','enable':[],'disable':[]},'设置损坏，已恢复默认值'


def save_settings(state,path=None):
    try:
        target=path or settings_path(); target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({'baseline':state.baseline,'enable':state.enable,'disable':state.disable,'board':state.board},indent=2),encoding='utf-8')
        return ''
    except OSError as exc: return f'无法保存设置: {exc}'


def build_run_command(state,output='build/workbench.s'):
    return [[sys.executable,'-m','tools.build',output,'--profile',state.baseline,
             *[arg for x in state.enable for arg in ('--enable',x)],
             *[arg for x in state.disable for arg in ('--disable',x)],'--qemu'],
            ['qemu-riscv32',str(Path(output).with_suffix('.elf'))]]


def board_arguments(board):
    addresses=core.BoardAddresses.from_mapping(board).as_dict()
    result=[]
    for key in ('uart_tx','vga_base','exit_status'):
        result.extend(['--'+key.replace('_','-'),hex(addresses[key])])
    return result


def build_hardware_command(state,source,output):
    return [sys.executable,'-m','tools.build',source,'-o',output,'--profile',state.baseline,
            *[arg for x in state.enable for arg in ('--enable',x)],
            *[arg for x in state.disable for arg in ('--disable',x)],*board_arguments(state.board)]
