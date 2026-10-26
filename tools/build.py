"""Optional external GNU build examples; select CPU21 or QEMU explicitly."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import re
from mycc import core
from mycc.cli import atomic_write, profile_from_args
from adapters import check_target,compile_options
from adapters.generic.config import BoardAddresses

ROOT=Path(__file__).resolve().parents[1]


def tool(name):
    for prefix in ('riscv-none-elf-','riscv64-unknown-elf-','riscv32-unknown-elf-','riscv64-linux-gnu-'):
        found=shutil.which(prefix+name)
        if found: return found
    raise RuntimeError('RISC-V '+name+' not found; install a RISC-V GNU toolchain')


def profile_args(p):
    p.add_argument('--target',choices=['generic','cpu21'],default='generic')
    p.add_argument('--profile',default=None); p.add_argument('--isa-file')
    p.add_argument('--enable',action='append',default=[]); p.add_argument('--disable',action='append',default=[])
    p.set_defaults(no_lui=False,no_vshift=False)


def invoke(args):
    subprocess.run([str(x) for x in args],check=True,timeout=30)


def build(source,profile=None,qemu=False,output=None,board=None,target='generic'):
    target='generic' if qemu else target
    profile=profile or core.load_profile('cpu21' if target=='cpu21' else 'PF-01')
    check_target(profile,target)
    if target=='cpu21':
        from adapters.cpu21 import CPU21Board,ASSETS
        from adapters.cpu21.assets import render_startup,export_rom
        addresses=(CPU21Board.from_mapping(board) if board is not None else CPU21Board()).as_dict()
    else: addresses=board or {}
    source=Path(source).absolute()
    out=Path(output).absolute() if output else ROOT/'build'/source.stem
    out.parent.mkdir(parents=True,exist_ok=True)
    asm=out.with_suffix('.s')
    if source.suffix=='.c':
        res=core.compile(core.SourceFile(source.read_text(encoding='utf-8-sig'),str(source)),profile,
                         options=compile_options(target))
        if not res.success:
            raise RuntimeError(''.join(core.format_diagnostic(d) for d in res.diagnostics))
        atomic_write(asm,res.asm)
    elif source.suffix=='.s':
        asm=source
        text=asm.read_text(encoding='utf-8-sig')
        if target=='cpu21' and ('# mycc-target: generic' in text or re.search(r'^\s*\.(word|4byte|byte)\b',text,re.M)):
            raise RuntimeError('CPU21 requires Harvard assembly without ROM data; recompile the C source with --target cpu21')
    else: raise RuntimeError('expected .c or .s')
    # I/O routines use the same compiler/profile, as a library translation unit.
    io=core.compile(core.SourceFile((ROOT/'runtime/io.c').read_text(),'<runtime/io.c>'),profile,
                    options=compile_options(target,require_main=False))
    if not io.success: raise RuntimeError(str(io.diagnostics))
    io_asm=out.with_suffix('.io.s'); atomic_write(io_asm,io.asm)
    objects=[]
    boot=ASSETS/'runtime/start.s' if target=='cpu21' else ROOT/('adapters/qemu/runtime.s' if qemu else 'adapters/generic/runtime/start.s')
    sources=[asm,ROOT/'runtime/runtime.s',boot,io_asm]
    if target=='cpu21':
        console=core.compile(core.SourceFile((ASSETS/'runtime/console.c').read_text(),'<runtime/console>'),profile,
                             options=compile_options(target,require_main=False))
        if not console.success: raise RuntimeError(str(console.diagnostics))
        console_asm=out.with_suffix('.console.s'); atomic_write(console_asm,console.asm); sources.append(console_asm)
    for i,path in enumerate(sources):
        if path.name in ('runtime.s','start.s','qemu.s'):
            lowered=out.with_suffix(f'.runtime{i}.s')
            text=path.read_text(encoding='utf-8')
            if target=='cpu21': text=render_startup(text,profile,addresses)
            atomic_write(lowered,core.lower_assembly(text,profile))
            path=lowered
        obj=out.with_suffix(f'.{i}.o'); objects.append(obj)
        invoke([tool('as'),'-march='+('rv32im_zicsr' if target=='cpu21' else 'rv32im'),'-mabi=ilp32','-mno-relax',
                '--defsym',f'HAVE_MUL={int(profile.has("mul"))}',
                '--defsym',f'HAVE_DIVREM={int(profile.has("div") and profile.has("rem"))}',
                '--defsym',f'HAVE_VSHIFT={int(profile.has("sll"))}',path,'-o',obj])
    elf=out.with_suffix('.elf')
    symbols=[arg for key,value in sorted(addresses.items()) for arg in ('--defsym',f'__{key}={value}')]
    linker=ASSETS/'linker.ld' if target=='cpu21' else ROOT/('adapters/qemu/linker.ld' if qemu else 'adapters/generic/linker.ld')
    invoke([tool('ld'),'-m','elf32lriscv','--no-relax',*symbols,'-T',linker,*objects,'-o',elf])
    invoke([tool('objcopy'),'-O','binary',elf,out.with_suffix('.bin')])
    invoke([tool('objcopy'),'-O','verilog',elf,out.with_suffix('.bytes.hex')])
    blob=out.with_suffix('.bin').read_bytes()
    if target=='cpu21':
        export_rom(blob,out)
    else:
        atomic_write(out.with_suffix('.hex'),out.with_suffix('.bytes.hex').read_text())
        atomic_write(out.with_suffix('.logisim.hex'),'v2.0 raw\n'+' '.join(f'{b:02x}' for b in blob)+'\n')
    from .lint import lint
    violations=lint(elf,profile,qemu=qemu,target=target)
    if violations: raise RuntimeError('\n'.join(violations))
    import json
    import hashlib
    atomic_write(out.with_suffix('.manifest.json'),json.dumps({
        'target':target,'qemu':qemu,'profile':profile.name,'profile_fingerprint':profile.fingerprint,
        'instructions':sorted(profile.instructions),'mmio':addresses,
        'rom_word_bits':32 if target=='cpu21' else 8,
        'rom_words':8192 if target=='cpu21' else None,
        'binary_sha256':hashlib.sha256(blob).hexdigest(),
    },indent=2)+'\n')
    return elf



def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('source'); p.add_argument('-o','--output'); p.add_argument('--qemu',action='store_true'); profile_args(p)
    p.add_argument('--board-file',help='MMIO JSON for the selected target')
    for key in ('uart-tx','vga-base','exit-status'): p.add_argument('--'+key)
    for key in ('led','seg','display-ctrl','display-cursor','mouse-ctrl'): p.add_argument('--'+key)
    a=p.parse_args(argv)
    try:
        import json
        if a.qemu: a.target='generic'
        if a.target=='cpu21':
            from adapters.cpu21 import CPU21Board
            kind=CPU21Board
        else: kind=BoardAddresses
        board=kind().as_dict()
        if a.board_file:
            board=json.loads(Path(a.board_file).read_text(encoding='utf-8'))
            kind.from_mapping(board)
        if a.target=='cpu21' and (a.uart_tx is not None or a.exit_status is not None):
            raise ValueError('CPU21 has no UART/exit register; use --led and --seg for the exit status')
        for key in board:
            if getattr(a,key) is not None: board[key]=getattr(a,key)
        board=kind.from_mapping(board).as_dict()
        elf=build(a.source,profile_from_args(a),a.qemu,a.output,None if a.qemu else board,a.target)
        print(elf); return 0
    except (OSError,ValueError,RuntimeError,core.ProfileError,subprocess.SubprocessError) as exc:
        print('build: '+str(exc),file=sys.stderr); return 1


if __name__=='__main__': raise SystemExit(main())
