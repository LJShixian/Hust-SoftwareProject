"""One-command checks; --full makes unavailable external tools a failure."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from .check_architecture import check
from .check_docs import check as docs_check
from .build import ROOT,tool


def source_hashes():
    """Digest every input that can change the artifact, plus the committed specs.

    A report is only evidence if it names the tree it was produced from, so this
    manifest is written next to the coverage report on every run.
    """
    paths=[]
    for folder in ('mycc','adapters','tools','runtime','configs','examples','tests','scripts'):
        paths.extend(sorted((ROOT/folder).rglob('*')))
    paths.extend(sorted((ROOT/'docs/specs').rglob('*.md')))
    paths.extend(ROOT/name for name in ('README.md','pyproject.toml','requirements.txt','THIRD_PARTY.md'))
    digests={}
    for path in paths:
        if not path.is_file() or '__pycache__' in path.parts: continue
        digests[str(path.relative_to(ROOT)).replace('\\','/')]=hashlib.sha256(path.read_bytes()).hexdigest()
    trees=hashlib.sha256(json.dumps(digests,sort_keys=True).encode()).hexdigest()
    payload={'schema':'mycc-source-hashes/1','file_count':len(digests),'tree':trees,'files':digests}
    (ROOT/'build/reports/source-hashes.json').write_text(json.dumps(payload,indent=1,sort_keys=True),encoding='utf-8')
    return payload


def main():
    p=argparse.ArgumentParser(); p.add_argument('--full',action='store_true')
    p.add_argument('--cpu21',action='store_true',help='verify production firmware on original CPU21 RTL')
    p.add_argument('--fpga-root',type=Path)
    args=p.parse_args()
    (ROOT/'build/reports').mkdir(parents=True,exist_ok=True)
    errors=check()
    if errors:
        print('\n'.join(errors)); return 1
    print('architecture: ok',flush=True)
    drift=docs_check()
    if drift:
        print('\n'.join(drift)); return 1
    print('docs: preset table and JSON reference sets agree with core/isa.py',flush=True)
    if args.full:
        try: tool('as'); tool('gcc')
        except RuntimeError as exc: print(exc); return 1
        if not shutil.which('qemu-riscv32'):
            print('full acceptance requires qemu-riscv32; runtime verification is unavailable'); return 1
    measured=bool(importlib.util.find_spec('coverage'))
    command=[sys.executable,'-m','coverage','run','-m','pytest','-q'] if measured else [sys.executable,'-m','pytest','-q']
    code=subprocess.run(command,cwd=ROOT).returncode
    if code: return code
    if measured:
        subprocess.run([sys.executable,'-m','coverage','report'],cwd=ROOT,check=True)
        subprocess.run([sys.executable,'-m','coverage','json','-o','build/reports/coverage.json'],cwd=ROOT,check=True)
        data=json.loads((ROOT/'build/reports/coverage.json').read_text())['files']
        def summary(prefix):
            files=[v['summary'] for k,v in data.items() if prefix in k.replace('\\','/')]
            covered=sum(s['covered_lines'] for s in files); total=sum(s['num_statements'] for s in files)
            bc=sum(s.get('covered_branches',0) for s in files); bt=sum(s.get('num_branches',0) for s in files)
            return covered/max(1,total)*100,bc/max(1,bt)*100
        targets=[('mycc/core/',80),('mycc/core/codegen.py',90),('mycc/core/sema.py',90),('mycc/core/isa.py',90),('mycc/cli.py',70)]
        if importlib.util.find_spec('PySide6'): targets.append(('mycc/gui/',60))
        for name,minimum in targets:
            percent,_=summary(name)
            if percent<minimum: print(f'coverage gate failed: {name} {percent:.1f}% < {minimum}%'); return 1
        if summary('mycc/core/')[1]<60: print('core branch coverage below 60%'); return 1
        print('coverage gates: ok')
        manifest=source_hashes()
        print(f'source hashes: {manifest["file_count"]} files, tree {manifest["tree"][:16]}')
    elif args.full:
        print('coverage is required for full acceptance'); return 1
    if not shutil.which('qemu-riscv32'):
        print('LIMITATION: qemu-riscv32 missing; execution and GCC comparison remain unverified.')
    else:
        from .compare import compare
        for program in ('hello','fib','arrays','control','shifts'):
            compare(ROOT/'examples/compiler'/f'{program}.c',output=ROOT/'build'/'compare'/program)
        print('GCC execution comparison: ok')
    if args.cpu21:
        from .verify_cpu21 import verify,DEFAULT_FPGA
        try: report=verify(args.fpga_root or DEFAULT_FPGA)
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
            print('CPU21 acceptance failed: '+str(exc)); return 1
        print(f'CPU21 acceptance: {len(report["results"])} production firmware cases passed; hardware source unchanged')
    return 0


if __name__=='__main__': raise SystemExit(main())
