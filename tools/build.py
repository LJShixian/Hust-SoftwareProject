"""Portable build equivalent of scripts/build.sh."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from mycc import core
from mycc.cli import atomic_write, profile_from_args

ROOT=Path(__file__).resolve().parents[1]


def tool(name):
    for prefix in ('riscv-none-elf-','riscv64-unknown-elf-','riscv32-unknown-elf-','riscv64-linux-gnu-'):
        found=shutil.which(prefix+name)
        if found: return found
    raise RuntimeError('RISC-V '+name+' not found; install a RISC-V GNU toolchain')


def profile_args(p):
    p.add_argument('--profile',default='PF-01'); p.add_argument('--isa-file')
    p.add_argument('--enable',action='append',default=[]); p.add_argument('--disable',action='append',default=[])
    p.set_defaults(no_lui=False,no_vshift=False)


def invoke(args):
    subprocess.run([str(x) for x in args],check=True,timeout=30)


def build(source,profile,qemu=False,output=None,board=None):
    source=Path(source).absolute()
    out=Path(output).absolute() if output else ROOT/'build'/source.stem
    out.parent.mkdir(parents=True,exist_ok=True)
    asm=out.with_suffix('.s')
    if source.suffix=='.c':
        res=core.compile(core.SourceFile(source.read_text(encoding='utf-8-sig'),str(source)),profile)
        if not res.success:
            raise RuntimeError(''.join(core.format_diagnostic(d) for d in res.diagnostics))
        atomic_write(asm,res.asm)
    elif source.suffix=='.s':
        asm=source
    else: raise RuntimeError('expected .c or .s')
    # I/O routines use the same compiler/profile, as a library translation unit.
    io=core.compile(core.SourceFile((ROOT/'runtime/io.c').read_text(),'<runtime/io.c>'),profile,
                    options=core.CompileOptions(require_main=False))
    if not io.success: raise RuntimeError(str(io.diagnostics))
    io_asm=out.with_suffix('.io.s'); atomic_write(io_asm,io.asm)
    objects=[]
    sources=[asm,ROOT/'runtime/runtime.s',ROOT/('runtime/qemu.s' if qemu else 'runtime/start.s'),io_asm]
    for i,path in enumerate(sources):
        if path.name in ('runtime.s','start.s','qemu.s'):
            lowered=out.with_suffix(f'.runtime{i}.s')
            atomic_write(lowered,core.lower_assembly(path.read_text(encoding='utf-8'),profile))
            path=lowered
        obj=out.with_suffix(f'.{i}.o'); objects.append(obj)
        invoke([tool('as'),'-march=rv32im','-mabi=ilp32','-mno-relax',
                '--defsym',f'HAVE_MUL={int(profile.has("mul"))}',
                '--defsym',f'HAVE_DIVREM={int(profile.has("div") and profile.has("rem"))}',
                '--defsym',f'HAVE_VSHIFT={int(profile.has("sll"))}',path,'-o',obj])
    elf=out.with_suffix('.elf')
    board=board or {}
    symbols=[arg for key,value in sorted(board.items()) for arg in ('--defsym',f'__{key}={value}')]
    invoke([tool('ld'),'-m','elf32lriscv','--no-relax',*symbols,'-T',ROOT/('linker/qemu.ld' if qemu else 'linker/link.ld'),*objects,'-o',elf])
    invoke([tool('objcopy'),'-O','binary',elf,out.with_suffix('.bin')])
    invoke([tool('objcopy'),'-O','verilog',elf,out.with_suffix('.hex')])
    blob=out.with_suffix('.bin').read_bytes()
    # Byte-addressed readmemh format is also compatible with Logisim v2 raw.
    atomic_write(out.with_suffix('.logisim.hex'),'v2.0 raw\n'+' '.join(f'{b:02x}' for b in blob)+'\n')
    from .lint import lint
    violations=lint(elf,profile,qemu=qemu)
    if violations: raise RuntimeError('\n'.join(violations))
    return elf


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('source'); p.add_argument('-o','--output'); p.add_argument('--qemu',action='store_true'); profile_args(p)
    p.add_argument('--board-file',help='JSON containing uart_tx, vga_base and exit_status')
    for key in ('uart-tx','vga-base','exit-status'): p.add_argument('--'+key)
    a=p.parse_args(argv)
    try:
        import json
        board={'uart_tx':'0x10000000','vga_base':'0x20000000','exit_status':'0x10000004'}
        if a.board_file:
            board=json.loads(Path(a.board_file).read_text(encoding='utf-8'))
            core.BoardAddresses.from_mapping(board)
        for key in ('uart_tx','vga_base','exit_status'):
            if getattr(a,key) is not None: board[key]=getattr(a,key)
        board=core.BoardAddresses.from_mapping(board).as_dict()
        elf=build(a.source,profile_from_args(a),a.qemu,a.output,None if a.qemu else board)
        print(elf); return 0
    except (OSError,ValueError,RuntimeError,core.ProfileError,subprocess.SubprocessError) as exc:
        print('build: '+str(exc),file=sys.stderr); return 1


if __name__=='__main__': raise SystemExit(main())
