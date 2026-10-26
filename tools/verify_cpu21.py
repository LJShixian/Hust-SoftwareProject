"""Run production CPU21 firmware against an external, strictly read-only RTL tree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from mycc import core
from .build import ROOT,build

DEFAULT_FPGA=Path(os.environ.get('MYCC_CPU21_ROOT',r'D:\Xilinx\Project\risc-v'))


def snapshot(root):
    """Hash tracked and unignored files without importing/running project code."""
    names=subprocess.check_output(['rg','--files','--hidden','-g','!.git',str(root)],text=True).splitlines()
    return {str(Path(name).relative_to(root)):hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in names}


def run_command(args,cwd,log,timeout=60):
    proc=subprocess.run([str(a) for a in args],cwd=cwd,capture_output=True,text=True,errors='replace',timeout=timeout)
    Path(log).write_text(proc.stdout+proc.stderr,encoding='utf-8')
    if proc.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed; see {log}\n'+(proc.stdout+proc.stderr)[-2000:])
    return proc.stdout+proc.stderr


def glyph(char):
    if 'a'<=char<='z': char=char.upper()
    if 'A'<=char<='Z': return ord(char)-ord('A')+16
    if '1'<=char<='8': return int(char)
    return {'0':30,'9':32,' ':0,'-':14}.get(char,13)


def expected_screen(text):
    cells=[0]*1200; position=0
    for char in text:
        if char=='\n': position=(position//40+1)*40
        elif char=='\r': position-=position%40
        elif char=='\t':
            for _ in range(4-position%4): cells[position]=0x700; position=(position+1)%1200
        else: cells[position]=0x700|glyph(char); position+=1
        if position>=1200: position=0
    return [cells[i]|cells[i+1]<<16 for i in range(0,1200,2)]


OUTPUTS={
    'compiler_demo':'55\n',
    'hello':'Hi\n42\n0x80000000\n','fib':'55\n','arrays':'1 5 15\n',
    'control':'0 19\n','muldiv':'-85 -3 -2\n-85 -3 2\n85 3 -2\n-2147483648 -2147483648 0\n0 -1 123\n',
    'shifts':'0x468acf00 0xfc000000 0x64606468\n','pointers':'3 7 16\n',
    'cpu21_selftest':'PASS\n','cpu21_vga':'','cpu21_wrap':'A'*1201+'B','cpu21_stack':'','cpu21_large_frame':'',
}


def verify(root=DEFAULT_FPGA,output=None,cases=None):
    root=Path(root).resolve(); out=Path(output or ROOT/'build/cpu21-verification').resolve()
    if out==root or out.is_relative_to(root): raise ValueError('verification output must not be inside the FPGA project')
    rtl=root/'pipelined-cpu/srcs/rtl'
    if not (rtl/'cpu21_riscv_redirect_int_bpb.v').is_file(): raise RuntimeError('CPU21 RTL not found: '+str(rtl))
    tools={name:shutil.which(name) for name in ('xvlog','xelab','xsim')}
    if not all(tools.values()): raise RuntimeError('Vivado xvlog/xelab/xsim must be on PATH')
    out.mkdir(parents=True,exist_ok=True)
    before=snapshot(root); started=time.monotonic(); results=[]
    (out/'source-before.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    try:
        run_command([tools['xvlog'],'-sv',*sorted(rtl.glob('*.v')),ROOT/'tests/rtl/cpu21_program_tb.v'],out,out/'xvlog.log')
        run_command([tools['xelab'],'work.cpu21_program_tb','-s','cpu21_program','-debug','typical'],out,out/'xelab.log')
        cases=cases or [(name,[]) for name in OUTPUTS]+[('arrays',['lui']),('shifts',['vshift']),('muldiv',['mul']),('cpu21_selftest',['lui','vshift']),('compiler_demo',['mul'])]
        for index,(name,disabled) in enumerate(cases):
            profile=core.load_profile('cpu21',disable=disabled)
            stem=out/f'{index:02}-{name}'
            elf=build(ROOT/'examples'/('cpu21' if name.startswith('cpu21_') else 'compiler')/f'{name}.c',profile,output=stem,target='cpu21')
            fb=stem.with_suffix('.fb.hex'); log=stem.with_suffix('.xsim.log')
            # The option file preserves '=' through Vivado's Windows batch wrapper.
            args=stem.with_suffix('.args')
            args.write_text(f'-runall\n-testplusarg ROM={elf.with_suffix(".hex").as_posix()}\n-testplusarg FB={fb.as_posix()}\n-log {log.as_posix()}\n',encoding='utf-8')
            console=run_command([tools['xsim'],'cpu21_program','-f',args],out,stem.with_suffix('.console.txt'))
            result=re.search(r'CPU21_RESULT=(\d+) CYCLES=(\d+) CURSOR=([0-9a-f]+) CTRL=([0-9a-f]+)',console)
            if not result: raise RuntimeError(f'{name}: simulation did not reach exit; see {log}')
            actual=[int(line.strip(),16) for line in fb.read_text().splitlines() if re.fullmatch(r'[0-9a-fA-F]{8}',line.strip())]
            expected=expected_screen(OUTPUTS[name])
            if name=='cpu21_vga':
                expected[0]=0x02110110; expected[599]=0x07290000
                if int(result[3],16)!=0x1d27 or int(result[4],16)!=1:
                    raise RuntimeError('VGA cursor position/enable mismatch')
            expected_status=0x5354414b if name in ('cpu21_stack','cpu21_large_frame') else 0
            if int(result[1])!=expected_status: raise RuntimeError(f'{name}: exit status {result[1]}, expected {expected_status}')
            if actual!=expected:
                differences=[i for i,(a,b) in enumerate(zip(actual,expected)) if a!=b]
                raise RuntimeError(f'{name}: VGA mismatch at words {differences[:10]}, got {len(actual)} words')
            item={'program':name,'disabled':disabled,'exit_status':int(result[1]),'cycles':int(result[2]),'vga_words_verified':len(actual)}
            results.append(item); print('CPU21 PASS '+json.dumps(item),flush=True)
    finally:
        after=snapshot(root)
        readonly={'files_checked':len(before),'unchanged':before==after,'changed':[p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)]}
        report={'results':results,'read_only':readonly,'elapsed_seconds':time.monotonic()-started}
        (out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        (out/'source-after.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
        if not readonly['unchanged']: raise RuntimeError('FPGA project changed during verification: '+str(readonly['changed']))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,default=DEFAULT_FPGA); p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        report=verify(a.root,a.output)
        print(f'CPU21: {len(report["results"])} production firmware cases passed; FPGA source hashes unchanged')
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        print('CPU21 verification failed: '+str(exc)); return 1


if __name__=='__main__': raise SystemExit(main())
