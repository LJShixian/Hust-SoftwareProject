"""Real GNU assembler/linker/lint matrix. QEMU execution is never simulated."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import subprocess
import pytest
from mycc import core
from tools.build import build,tool,ROOT
from tools.lint import lint

PROFILES=[(f'PF-{i:02}',[],[]) for i in range(1,8)]+[('PF-01',['div'],[]),('PF-01',['mul'],['lui'])]
PROGRAMS=['hello','fib','arrays','control','muldiv','shifts']
EXPECTED={'hello':'Hi\n42\n0x80000000\n','fib':'55\n','arrays':'1 5 15\n','control':'0 19\n',
          'muldiv':'-85 -3 -2\n-85 -3 2\n85 3 -2\n-2147483648 -2147483648 0\n0 -1 123\n',
          'shifts':'0x468acf00 0xfc000000 0x64606468\n','pointers':'3 7 16\n'}


@pytest.fixture(scope='module')
def assembled_matrix(tmp_path_factory):
    try: tool('as')
    except RuntimeError: pytest.skip('RISC-V GNU toolchain unavailable')
    root=tmp_path_factory.mktemp('matrix')
    jobs=[(i,profile,name) for i,profile in enumerate(PROFILES) for name in PROGRAMS]
    def worker(job):
        i,(name,enable,disable),program=job
        p=core.load_profile(name,enable,disable)
        # Linux executable provides an independent optional execution path.
        out=root/f'p{i}'/program
        elf=build(ROOT/'bench'/f'{program}.c',p,True,out)
        return i,program,p,elf
    with ThreadPoolExecutor(max_workers=4) as pool: return list(pool.map(worker,jobs))


def test_real_assembler_profile_matrix(assembled_matrix):
    assert len(assembled_matrix)==54
    for _,_,p,elf in assembled_matrix: assert not lint(elf,p,True)


def test_runtime_behavior_profile_matrix(assembled_matrix):
    qemu=shutil.which('qemu-riscv32')
    if not qemu: pytest.skip('qemu-riscv32 unavailable: execution matrix not verified')
    for _,name,_,elf in assembled_matrix:
        proc=subprocess.run([qemu,str(elf)],capture_output=True,timeout=30)
        assert proc.returncode==0
        assert proc.stdout.decode()==EXPECTED[name]


def test_bare_metal_no_lui_and_no_vshift(tmp_path):
    try: tool('as')
    except RuntimeError: pytest.skip('RISC-V GNU toolchain unavailable')
    p=core.load_profile('PF-01',disable=['lui','vshift'])
    elf=build(ROOT/'bench/arrays.c',p,False,tmp_path/'arrays')
    assert not lint(elf,p)


def test_lint_sensitive_to_profile(tmp_path):
    try: tool('as')
    except RuntimeError: pytest.skip('RISC-V GNU toolchain unavailable')
    src=tmp_path/'wide.s'
    src.write_text('.option norvc\n.text\n.globl demo\ndemo:\nmul a0,a0,a1\njalr zero,0(ra)\n')
    obj=tmp_path/'wide.o'
    subprocess.run([tool('as'),'-march=rv32im','-mabi=ilp32',str(src),'-o',str(obj)],check=True)
    assert lint(obj,core.load_profile('PF-01'))
    assert not lint(obj,core.load_profile('PF-05'))


def test_minimum_isa_codegen_assembles(tmp_path):
    try: tool('as')
    except RuntimeError: pytest.skip('RISC-V GNU toolchain unavailable')
    p=core.load_profile(disable=sorted(core.ALL-core.MV_ISA))
    r=core.compile(core.SourceFile('int x;int main(){int n=3; x=(0x12345678^5)>>n; return x&7;}'),p)
    assert r.success
    src=tmp_path/'minimal.s'; src.write_text(r.asm)
    obj=tmp_path/'minimal.o'
    subprocess.run([tool('as'),'-march=rv32i','-mabi=ilp32',str(src),'-o',str(obj)],check=True)
    assert not lint(obj,p)


def test_runtime_minimum_isa_assembles(tmp_path):
    try: tool('as')
    except RuntimeError: pytest.skip('RISC-V GNU toolchain unavailable')
    p=core.load_profile(disable=sorted(core.ALL-core.MV_ISA))
    src=tmp_path/'runtime.s'; src.write_text(core.lower_assembly((ROOT/'runtime/runtime.s').read_text(),p))
    obj=tmp_path/'runtime.o'
    subprocess.run([tool('as'),'-march=rv32i','-mabi=ilp32',str(src),'-o',str(obj)],check=True)
    assert not lint(obj,p)
