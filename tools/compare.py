"""Run defined-behavior benchmarks with mycc and GCC on Linux-user QEMU."""
from pathlib import Path
import argparse
import shutil
import subprocess
import sys
from .build import ROOT,tool,build,invoke
from mycc import core
from mycc.cli import atomic_write


def compare(source,profile=None,output=None):
    qemu=shutil.which('qemu-riscv32')
    if not qemu: raise RuntimeError('qemu-riscv32 missing; comparison cannot run')
    profile=profile or core.load_profile()
    output=Path(output or ROOT/'build'/'compare')
    myelf=build(source,profile,True,output/'mycc')
    gcc=tool('gcc'); objects=[]
    declarations='void putchar(int); void printint(int); void printhex(int);\n'
    header=output/'builtins.h'; atomic_write(header,declarations)
    for i,path in enumerate([Path(source),ROOT/'runtime/io.c']):
        obj=output/f'gcc{i}.o'; objects.append(obj)
        args=[gcc,'-march=rv32i','-mabi=ilp32','-O0','-fwrapv','-fno-builtin','-fno-pic','-fno-pie',
              '-mno-relax','-msmall-data-limit=0','-ffreestanding','-include',header,'-c',path,'-o',obj]
        if i==1: args.insert(1,'-Dmain=__runtime_unused_main')
        invoke(args)
    # Link GCC output against exactly the same software arithmetic and I/O shim.
    for i,path in enumerate([ROOT/'runtime/runtime.s',ROOT/'runtime/qemu.s']):
        obj=output/f'asm{i}.o'; objects.append(obj)
        invoke([tool('as'),'-march=rv32i','-mabi=ilp32','-mno-relax',path,'-o',obj])
    gccelf=output/'gcc.elf'
    invoke([tool('ld'),'-m','elf32lriscv','--no-relax','-T',ROOT/'linker/qemu.ld',*objects,'-o',gccelf])
    results=[subprocess.run([qemu,str(elf)],capture_output=True,timeout=30) for elf in (myelf,gccelf)]
    a,b=results
    if (a.returncode,a.stdout,a.stderr)!=(b.returncode,b.stdout,b.stderr):
        raise RuntimeError(f'GCC mismatch: mycc={(a.returncode,a.stdout,a.stderr)!r}; gcc={(b.returncode,b.stdout,b.stderr)!r}')
    return a.stdout


def main():
    p=argparse.ArgumentParser(); p.add_argument('source'); a=p.parse_args()
    try: compare(a.source); print('compare: stdout/stderr/exit status match'); return 0
    except (OSError,RuntimeError,subprocess.SubprocessError) as exc: print('compare: '+str(exc),file=sys.stderr); return 1


if __name__=='__main__': raise SystemExit(main())
