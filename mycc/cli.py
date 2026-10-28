"""CLI filesystem boundary; output is committed only after successful compilation."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from . import __version__
from . import core
from .rars import convert as to_rars

ROOT = Path(__file__).resolve().parents[1]


class ArgumentParser(argparse.ArgumentParser):
    def error(self,message):
        self.print_usage(sys.stderr)
        self.exit(64,f'mycc: error: {message}\n')


def parser():
    p=ArgumentParser(prog='mycc',description='C subset → capability-driven RISC-V RV32 assembly')
    p.add_argument('source',nargs='?')
    p.add_argument('-o',default='a.s')
    p.add_argument('--version',action='version',version=f'mycc {__version__} | Python {sys.version_info.major}.{sys.version_info.minor} | ISA schema 1')
    external=p.add_argument_group('可选外部适配（普通编译无需设置）')
    external.add_argument('--target',choices=['generic','cpu21','logisim'],default='generic')
    external.add_argument('--rars',action='store_true',
                          help='emit one self-contained .asm for the RARS simulator instead of GNU assembly')
    external.add_argument('--logisim',action='store_true',
                          help='with --rars, also emit Logisim v2.0 raw ROM/RAM images next to -o')
    external.add_argument('--stack-top',type=lambda text:int(text,0),default=None,
                          help='value loaded into sp by the RARS entry stub (default 1024 with --logisim)')
    p.add_argument('--profile',default=None)
    p.add_argument('--isa-file')
    p.add_argument('--enable',action='append',default=[])
    p.add_argument('--disable',action='append',default=[])
    p.add_argument('--no-lui',action='store_true')
    p.add_argument('--no-vshift',action='store_true')
    for flag in ('tokens','ast','ir','isa','isa-whitelist','lowering-report'):
        p.add_argument('--dump-'+flag,action='store_true')
    p.add_argument('--stats',action='store_true')
    p.add_argument('--doctor',action='store_true')
    p.add_argument('--gui',action='store_true')
    return p


def profile_from_args(args):
    data=None
    if args.isa_file:
        try: data=json.loads(Path(args.isa_file).read_text(encoding='utf-8-sig'))
        except (OSError,UnicodeError,json.JSONDecodeError) as exc: raise core.ProfileError(f'cannot read ISA profile: {exc}') from exc
    disable=list(args.disable)
    if args.no_lui: disable.append('lui')
    if args.no_vshift: disable.append('vshift')
    target=getattr(args,'target','generic')
    profile=core.load_profile(args.profile or ('cpu21' if target=='cpu21' else ('logisim' if target=='logisim' else 'PF-01')),args.enable,disable,data)
    if target!='generic':
        from adapters import check_target
        check_target(profile,target)
    return profile


def atomic_write(path,text):
    destination=Path(path).absolute()
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',newline='\n',dir=destination.parent,prefix='.mycc-tmp-',delete=False) as f:
            tmp=f.name; f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,destination)
        tmp=None
    finally:
        if tmp: Path(tmp).unlink(missing_ok=True)


def doctor():
    print('Python : ok '+sys.version.split()[0])
    print('core/cli dependencies : ok (standard library only)')
    print('PySide6 : '+('ok' if importlib.util.find_spec('PySide6') else 'missing (optional; pip install -r requirements.txt)'))
    print('display : '+('ok' if os.name=='nt' or sys.platform=='darwin' or os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') or os.environ.get('QT_QPA_PLATFORM')=='offscreen' else 'missing (CLI available)'))
    for name in ('riscv-none-elf-as','riscv64-unknown-elf-as','qemu-riscv32'):
        print(name+' : '+(shutil.which(name) or 'missing'))
    print('offline GUI installation : python -m pip install --no-index --find-links wheels -r requirements.txt')
    return 0


def run(argv=None):
    p=parser(); args=p.parse_args(argv)
    if args.doctor: return doctor()
    if args.gui:
        from .gui.app import launch
        return launch(args.source)
    if not args.source and not (args.dump_isa or args.dump_isa_whitelist): p.error('provide one .c source file, --gui, --doctor or --dump-isa')
    if args.target == 'logisim':
        # The classroom target is one command: listing plus ROM/RAM images.
        args.rars = True
        args.logisim = True
    if (args.rars or args.logisim) and args.target not in ('generic','logisim'):
        # The RARS file has no board addresses or MMIO; claiming a board target
        # would silently drop the layout the user asked for.
        print('mycc: error: --rars/--logisim cannot be combined with --target '+args.target
              +'; RARS output is a single generic listing',file=sys.stderr); return 64
    try: profile=profile_from_args(args)
    except core.ProfileError as exc:
        print(f'mycc: error: {exc}',file=sys.stderr); return exc.exit_code
    if args.dump_isa: sys.stdout.write(core.dump_isa(profile))
    if args.dump_isa_whitelist: sys.stdout.write(core.dump_isa_whitelist(profile))
    if not args.source: return 0
    if Path(args.source).suffix.lower()!='.c': p.error('source must have a .c extension')
    try:
        raw=Path(args.source).read_bytes()
        if len(raw)>128*1024: raise ValueError('source exceeds 128 KiB')
        text=raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        prefix=raw[:exc.start].decode('utf-8',errors='replace')
        line=prefix.count('\n')+1; col=len(prefix.rsplit('\n',1)[-1])+1
        print(f'{args.source}:{line}:{col}: error: invalid UTF-8 at byte offset {exc.start}',file=sys.stderr); return 65
    except (OSError,ValueError) as exc:
        print(f'{args.source}:1:1: error: {exc}',file=sys.stderr); return 65
    src=core.SourceFile(text,args.source)
    options=core.CompileOptions()
    if args.target!='generic':
        from adapters import compile_options
        options=compile_options(args.target)
    result=core.compile(src,profile,options=options)
    for d in result.diagnostics: sys.stderr.write(core.format_with_caret(d,src))
    for flag,fn in [('tokens',core.dump_tokens),('ast',core.dump_ast),('ir',core.dump_ir),('lowering_report',core.dump_lowering_report)]:
        if getattr(args,'dump_'+flag): sys.stdout.write(fn(result))
    if args.stats:
        for stage,ms in result.stages_ms.items(): print(f'{stage}\t{ms:.3f}',file=sys.stderr)
    if not result.success: return 1
    if args.logisim:
        # One C file becomes a loadable ROM/RAM pair: no Java, RARS or GNU toolchain.
        from .encode import AssembleError
        from .rars import images, ram_hex, rom_hex
        stack_top = args.stack_top if args.stack_top is not None else 1024
        # The image build writes up to three files, so creating the folder beats
        # failing on a path the user just typed for a classroom demo.
        try:
            Path(args.o).absolute().parent.mkdir(parents=True,exist_ok=True)
        except OSError as exc:
            print(f'mycc: error: cannot create output directory for {args.o}: {exc}',file=sys.stderr); return 70
        try:
            text,rom,ram = images(result.asm,profile=profile,stack_top=stack_top)
        except (ValueError,AssembleError) as exc:
            print(f'mycc: error: cannot build a Logisim image: {exc}',file=sys.stderr); return 70
        try:
            atomic_write(args.o,text)
            rom_path=Path(args.o).with_suffix('.rom.hex')
            atomic_write(rom_path,rom_hex(rom))
            if ram:
                ram_path=Path(args.o).with_suffix('.ram.hex')
                atomic_write(ram_path,ram_hex(ram))
        except OSError as exc:
            print(f'mycc: error: cannot write Logisim image next to {args.o}: {exc}',file=sys.stderr); return 70
        print(f'logisim: {rom_path.name} {len(rom)} words; sp={stack_top}'
              +(f'; {Path(args.o).with_suffix(".ram.hex").name} {len(ram)} words' if ram else '; no initialised data'))
        return 0
    text=to_rars(result.asm,profile=profile,stack_top=args.stack_top) if args.rars else result.asm
    try: atomic_write(args.o,text)
    except OSError as exc:
        print(f'mycc: error: cannot write {args.o}: {exc}',file=sys.stderr); return 70
    return 0


def main(argv=None):
    try: return run(argv)
    except KeyboardInterrupt: return 130
    except Exception as exc:
        print(f'mycc: internal compiler error: {type(exc).__name__}: {exc}',file=sys.stderr)
        return 2
