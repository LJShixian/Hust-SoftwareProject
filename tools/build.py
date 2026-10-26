"""Portable build equivalent of scripts/build.sh."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import re
from mycc import core
from mycc.cli import atomic_write, profile_from_args

ROOT=Path(__file__).resolve().parents[1]


def tool(name):
    for prefix in ('riscv-none-elf-','riscv64-unknown-elf-','riscv32-unknown-elf-','riscv64-linux-gnu-'):
        found=shutil.which(prefix+name)
        if found: return found
    raise RuntimeError('RISC-V '+name+' not found; install a RISC-V GNU toolchain')


def profile_args(p):
    p.add_argument('--target',choices=['cpu21','generic'],default='cpu21')
    p.add_argument('--profile',default=None); p.add_argument('--isa-file')
    p.add_argument('--enable',action='append',default=[]); p.add_argument('--disable',action='append',default=[])
    p.set_defaults(no_lui=False,no_vshift=False)


def invoke(args):
    subprocess.run([str(x) for x in args],check=True,timeout=30)


def build(source,profile=None,qemu=False,output=None,board=None,target='cpu21'):
    target='generic' if qemu else target
    profile=profile or core.load_profile('cpu21' if target=='cpu21' else 'PF-01')
    core.check_target(profile,target)
    addresses=(core.CPU21Board.from_mapping(board) if board is not None else core.CPU21Board()).as_dict() if target=='cpu21' else (board or {})
    source=Path(source).absolute()
    out=Path(output).absolute() if output else ROOT/'build'/source.stem
    out.parent.mkdir(parents=True,exist_ok=True)
    asm=out.with_suffix('.s')
    if source.suffix=='.c':
        res=core.compile(core.SourceFile(source.read_text(encoding='utf-8-sig'),str(source)),profile,
                         options=core.CompileOptions(target=target))
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
                    options=core.CompileOptions(require_main=False,target=target))
    if not io.success: raise RuntimeError(str(io.diagnostics))
    io_asm=out.with_suffix('.io.s'); atomic_write(io_asm,io.asm)
    objects=[]
    boot='runtime/qemu.s' if qemu else 'runtime/cpu21-start.s' if target=='cpu21' else 'runtime/start.s'
    sources=[asm,ROOT/'runtime/runtime.s',ROOT/boot,io_asm]
    if target=='cpu21':
        console=core.compile(core.SourceFile((ROOT/'runtime/cpu21-console.c').read_text(),'<runtime/console>'),profile,
                             options=core.CompileOptions(require_main=False,target=target))
        if not console.success: raise RuntimeError(str(console.diagnostics))
        console_asm=out.with_suffix('.console.s'); atomic_write(console_asm,console.asm); sources.append(console_asm)
    for i,path in enumerate(sources):
        if path.name in ('runtime.s','start.s','qemu.s','cpu21-start.s'):
            lowered=out.with_suffix(f'.runtime{i}.s')
            text=path.read_text(encoding='utf-8')
            if target=='cpu21' and not profile.has('lui'):
                def address_without_lui(match):
                    reg,symbol=match[1],match[2]
                    if symbol in ('__bss_start','__bss_end'):
                        return f'addi {reg},zero,%lo({symbol})\nslli {reg},{reg},20\nsrli {reg},{reg},20'
                    value=4096 if symbol=='__stack_top' else addresses[symbol[2:]]
                    count,remainder=divmod(value,2047)
                    return '\n'.join([f'addi {reg},zero,{remainder}']+[f'addi {reg},{reg},2047']*count)
                text=re.sub(r'lui (\w+),%hi\((\w+)\)\s*\n\s*addi \1,\1,%lo\(\2\)',address_without_lui,text)
            atomic_write(lowered,core.lower_assembly(text,profile))
            path=lowered
        obj=out.with_suffix(f'.{i}.o'); objects.append(obj)
        invoke([tool('as'),'-march='+('rv32im_zicsr' if target=='cpu21' else 'rv32im'),'-mabi=ilp32','-mno-relax',
                '--defsym',f'HAVE_MUL={int(profile.has("mul"))}',
                '--defsym',f'HAVE_DIVREM={int(profile.has("div") and profile.has("rem"))}',
                '--defsym',f'HAVE_VSHIFT={int(profile.has("sll"))}',path,'-o',obj])
    elf=out.with_suffix('.elf')
    symbols=[arg for key,value in sorted(addresses.items()) for arg in ('--defsym',f'__{key}={value}')]
    linker='linker/qemu.ld' if qemu else 'linker/cpu21.ld' if target=='cpu21' else 'linker/link.ld'
    invoke([tool('ld'),'-m','elf32lriscv','--no-relax',*symbols,'-T',ROOT/linker,*objects,'-o',elf])
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


def export_rom(blob,out):
    """CPU21 ROM: 8192 little-endian 32-bit words, plus a local include file."""
    if len(blob)>32768: raise RuntimeError('CPU21 ROM exceeds 32 KiB')
    blob+=b'\x00'*(-len(blob)%4)
    words=[int.from_bytes(blob[i:i+4],'little') for i in range(0,len(blob),4)]
    words += [0x13]*(8192-len(words))
    atomic_write(out.with_suffix('.hex'),''.join(f'{word:08x}\n' for word in words))
    atomic_write(out.with_suffix('.logisim.hex'),'v2.0 raw\n'+' '.join(f'{word:08x}' for word in words)+'\n')
    atomic_write(out.with_suffix('.vh'),'// CPU21 ROM include, generated locally; never written into FPGA project.\n'+
                 ''.join(f"rom[{i}] = 32'h{word:08x};\n" for i,word in enumerate(words)))


def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('source'); p.add_argument('-o','--output'); p.add_argument('--qemu',action='store_true'); profile_args(p)
    p.add_argument('--board-file',help='MMIO JSON for the selected target')
    for key in ('uart-tx','vga-base','exit-status'): p.add_argument('--'+key)
    for key in ('led','seg','display-ctrl','display-cursor','mouse-ctrl'): p.add_argument('--'+key)
    a=p.parse_args(argv)
    try:
        import json
        if a.qemu: a.target='generic'
        kind=core.CPU21Board if a.target=='cpu21' else core.BoardAddresses
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
