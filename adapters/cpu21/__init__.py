"""Optional CPU21 Harvard runtime, configuration and compiler policy."""
from mycc import core
from mycc.core.types import CodegenPolicy, INT, VOID
from .config import CPU21Board, CPU21_INSTRUCTIONS
from pathlib import Path

ASSETS=Path(__file__).resolve().parent

POLICY=CodegenPolicy(name='cpu21',globals_in_bss=True,initializer='__mycc_init_globals',
                     data_address_bits=12,stack_guard_symbol='__bss_end',
                     stack_guard_margin=128,stack_guard_trap='__mycc_stack_overflow')


def validate_profile(profile):
    missing=profile.instructions-CPU21_INSTRUCTIONS
    if missing:
        raise core.ProfileError('CPU21 does not implement: '+', '.join(sorted(missing))+
                                '; use --profile cpu21 or remove these instructions',64,'E-TARGET-ISA')


def options(**kwargs):
    return core.CompileOptions(target='cpu21',policy=POLICY,
        externals={'vga_cell':(VOID,[INT,INT,INT]),'vga_cursor':(VOID,[INT,INT])},**kwargs)


def compile(src,profile=None,**kwargs):
    profile=profile or core.load_profile('cpu21')
    validate_profile(profile)
    return core.compile(src,profile,options=options(**kwargs))


def board_arguments(board):
    addresses=CPU21Board.from_mapping(board).as_dict()
    return [arg for name,value in addresses.items() for arg in ('--'+name.replace('_','-'),hex(value))]
