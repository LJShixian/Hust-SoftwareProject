import json
import subprocess
import pytest
from mycc import core
from mycc.gui.workbench import WorkbenchState,board_arguments,build_hardware_command
from tools.build import build,tool,ROOT,main


@pytest.mark.parametrize('data',[
    {}, {'uart_tx':'bad','vga_base':0,'exit_status':4},
    {'uart_tx':3,'vga_base':0,'exit_status':4},
    {'uart_tx':-4,'vga_base':0,'exit_status':4},
    {'uart_tx':0x100000000,'vga_base':0,'exit_status':4},
])
def test_bad_mmio_address(data):
    with pytest.raises(ValueError): core.BoardAddresses.from_mapping(data)


def test_mmio_command_and_config():
    state=WorkbenchState(board={'uart_tx':'0x30000000','vga_base':'805310464','exit_status':'0x30000008'})
    args=board_arguments(state.board)
    assert args==['--uart-tx','0x30000000','--vga-base','0x30001000','--exit-status','0x30000008']
    command=build_hardware_command(state,'space file.s','space out.elf')
    assert command[3]=='space file.s' and '--qemu' not in command and '--uart-tx' in command


def test_custom_mmio_values_in_linked_elf(tmp_path):
    try: tool('as')
    except RuntimeError: pytest.skip('RISC-V toolchain missing')
    values={'uart_tx':0x30000000,'vga_base':0x30001000,'exit_status':0x30000008}
    elf=build(ROOT/'bench/hello.c',core.load_profile(),False,tmp_path/'board',values)
    symbols=subprocess.check_output([tool('nm'),str(elf)],text=True)
    assert '30000000 A __uart_tx' in symbols
    assert '30001000 A __vga_base' in symbols
    assert '30000008 A __exit_status' in symbols
    binary=elf.with_suffix('.bin').read_bytes()
    for value in values.values(): assert value.to_bytes(4,'little') in binary


def test_cli_board_file_and_override(tmp_path):
    try: tool('as')
    except RuntimeError: pytest.skip('RISC-V toolchain missing')
    config=tmp_path/'board.json'
    config.write_text(json.dumps(dict(uart_tx='0x30000000',vga_base='0x30001000',exit_status='0x30000008')))
    out=tmp_path/'firmware'
    assert main([str(ROOT/'bench/hello.c'),'-o',str(out),'--board-file',str(config),'--uart-tx','0x40000000'])==0
    symbols=subprocess.check_output([tool('nm'),str(out.with_suffix('.elf'))],text=True)
    assert '40000000 A __uart_tx' in symbols
    assert main([str(ROOT/'bench/hello.c'),'--uart-tx','0x3'])==1
