import subprocess
import sys
from pathlib import Path
import pytest
from mycc import core
from mycc.core.types import constant, div32, i32
from mycc.core.lexer import tokenize


def compile_text(text,profile='PF-01',**kwargs):
    return core.compile(core.SourceFile(text,'t.c'),core.load_profile(profile,**kwargs))


@pytest.mark.parametrize('profile,count',[(f'PF-{i:02}',n) for i,n in enumerate([26,25,23,32,29,30,39],1)])
def test_profile_counts(profile,count):
    # Counts follow the instruction sets; see DC-07 in implementation notes.
    p=core.load_profile(profile)
    assert len(p.instructions)==count
    assert len(core.dump_isa_whitelist(p).splitlines())==count


def test_profile_precedence_and_fingerprint():
    a=core.load_profile(enable=['m','lui'],disable=['div','lui'])
    assert a.has('mul') and a.has('rem') and not a.has('div') and not a.has('lui')
    b=core.load_profile(enable=['rem,mul'],disable=['lui'])
    assert a.fingerprint==b.fingerprint
    assert len(core.load_profile().fingerprint)==64


@pytest.mark.parametrize('data',[
    {}, {'name':'x','schema_version':2,'instructions':[]},
    {'name':'x','schema_version':1,'instructions':['add','add']},
    {'name':'x','schema_version':1,'instructions':['nonsense']},
    {'name':'x','schema_version':1,'instructions':[], 'typo':True},
])
def test_bad_profile(data):
    with pytest.raises(core.ProfileError): core.load_profile(data=data)


def test_missing_required_before_lexing():
    with pytest.raises(core.ProfileError) as exc: core.load_profile(disable=['jalr'])
    assert exc.value.exit_code==64


@pytest.mark.parametrize('text,expected',[
    ('int main(){return 1 }','E-PARSE-EXPECTED-TOKEN'),
    ('int main(){return missing;}','E-SEMA-UNDECLARED-ID'),
    ('int main(){int a; int a; return 0;}','E-SEMA-DUPLICATE-ID'),
    ('int main(){1=2;return 0;}','E-SEMA-LVALUE'),
    ('int main(){break;return 0;}','E-SEMA-LOOP-CONTROL'),
    ('int main(){continue;return 0;}','E-SEMA-LOOP-CONTROL'),
    ('int main(){printint();return 0;}','E-SEMA-ARGUMENTS'),
    ('void main(){return;}','E-SEMA-MAIN'),
    ('int main(){return putchar(65);}','E-SEMA-TYPE'),
    ('int main(){int* p; p=2;return 0;}','E-SEMA-TYPE'),
    ('int main(){int* p; return p*2;}','E-SEMA-TYPE'),
    ('int main(){int x;return x[0];}','E-SEMA-TYPE'),
    ('int main(){return *1;}','E-SEMA-TYPE'),
    ('int a[0]; int main(){return 0;}','E-SEMA-ARRAY-LENGTH'),
    ('int a[2]={1,2,3}; int main(){return 0;}','E-SEMA-TYPE'),
    ('int x=1/0; int main(){return 0;}','E-SEMA-CONSTANT'),
    ('#include <stdio.h>','E-UNSUPPORTED-CONSTRUCT'),
    ('int main(){char x;return 0;}','E-UNSUPPORTED-CONSTRUCT'),
    ('int main(){return (int)3;}','E-UNSUPPORTED-CONSTRUCT'),
    ('int main(){return 1?2:3;}','E-UNSUPPORTED-CONSTRUCT'),
    ('int main(){return "text";}','E-SEMA-TYPE'),
    ('/* never closed','E-LEX-UNCLOSED-COMMENT'),
    ('int main(){return @;}','E-LEX-UNEXPECTED-CHAR'),
    ('int main(){return 09;}','E-LEX-INVALID-INTEGER'),
    ('int main(){return 2147483648;}','E-LEX-INTEGER-RANGE'),
    ('int main(){return 0x100000000;}','E-LEX-INTEGER-RANGE'),
    ("int main(){return 'ab';}",'E-LEX-INVALID-CHAR'),
])
def test_diagnostics(text,expected):
    r=compile_text(text)
    assert not r.success and not r.asm
    assert r.diagnostics[0].code==expected
    assert r.diagnostics[0].line>0 and r.diagnostics[0].col>0


def test_diagnostic_position_and_caret():
    src=core.SourceFile('int main(){ return 1 }','t.c')
    r=core.compile(src)
    assert r.diagnostics[0].col==22
    assert "expected ';', got '}'" in core.format_with_caret(r.diagnostics[0],src)
    assert 't.c:1:22: error:' in core.format_with_caret(r.diagnostics[0],src)


def test_unicode_bom_comments_characters():
    src=core.SourceFile("\ufeff// 汉字\r\nint main(){ /*✓*/ return '\\n' + 010 + 0x10; }",'t.c')
    r=core.compile(src); assert r.success
    tokens=tokenize(src,core.MemoryReporter())
    assert tokens[0].line==2 and tokens[0].col==1
    assert [t.value for t in tokens if t.kind=='num']==[10,8,16]


def test_determinism_reentrancy_and_language_independence():
    src='int main(){int x=3; return x*7^2;}'
    a=compile_text(src); b=compile_text(src,'PF-07'); c=compile_text(src)
    assert a.asm==c.asm and a.asm!=b.asm
    assert compile_text('int main(){char x;}').diagnostics==compile_text('int main(){char x;}','PF-06').diagnostics


@pytest.mark.parametrize('profile,mnemonic,helper',[
    ('PF-01','jal ra,__mulsi3',True),('PF-05','mul a0,t0,a0',False),
])
def test_lowering_mul(profile,mnemonic,helper):
    r=compile_text('int main(){return 3*7;}',profile)
    assert mnemonic in r.asm
    assert bool('rejected' in core.dump_lowering_report(r)) is helper


def test_div_only_rem_lowering():
    r=compile_text('int main(){return 17%5;}',enable=['div'])
    assert 'div a1,t0,a0' in r.asm and 'jal ra,__mulsi3' in r.asm and '__modsi3' not in r.asm


def test_no_lui_no_variable_shift():
    r=compile_text('int x; int main(){int n=3;return (x+0x12345678)>>n;}',disable=['lui','vshift'])
    assert r.success and 'lui ' not in r.asm and '\nsra ' not in r.asm
    assert '__ashrsi3' in r.asm and '.word x' in r.asm


def test_abi_frame_arguments_and_scopes():
    r=compile_text('int f(int a,int b,int c,int d,int e,int f,int g,int h){return a+h;} int main(){int x=1;{int x=2;x++;}return f(x,2,3,4,5,6,7,8);}')
    assert r.success and 'sw a7,0(t0)' in r.asm
    assert 'lw a7,0(sp)' in r.asm


def test_sizeof_array_not_evaluated():
    r=compile_text('int main(){int a[4];int n=1;return sizeof(a)+sizeof(n++);}')
    assert r.success and 'addi a0,zero,16' in r.asm
    assert 'sw t1,0(t0)' not in r.asm


def test_cancel_and_size_limit():
    r=core.compile(core.SourceFile('int main(){return 0;}'),options=core.CompileOptions(cancelled=lambda:True))
    assert r.cancelled and not r.asm
    assert not compile_text(' '*131073).success


def test_nesting_limit_is_diagnostic():
    for text in ['int main(){return '+'('*220+'1'+')'*220+';}',
                 'int main(){'+'{'*110+'}'*110+'return 0;}']:
        r=compile_text(text); assert not r.success
        assert r.diagnostics[0].code=='E-PARSE-NESTING-LIMIT'


@pytest.mark.parametrize('a,b,q,r',[(17,5,3,2),(-17,5,-3,-2),(17,-5,-3,2),(-2147483648,-1,-2147483648,0),(123,0,-1,123)])
def test_integer_semantics(a,b,q,r):
    assert div32(a,b)==q and i32(a-q*b)==r


def test_cli_atomic_failure_preserves_output(tmp_path):
    src=tmp_path/'bad.c'; out=tmp_path/'old.s'
    out.write_text('previous successful result')
    src.write_text('int main(){return missing;}')
    p=subprocess.run([sys.executable,'-m','mycc',str(src),'-o',str(out)],capture_output=True,text=True)
    assert p.returncode==1 and out.read_text()=='previous successful result'
    assert not list(tmp_path.glob('.mycc-tmp-*'))


def test_cli_success_dump_and_exit_codes(tmp_path):
    src=tmp_path/'test.c'; out=tmp_path/'test.s'; src.write_text('int main(){return 42;}')
    p=subprocess.run([sys.executable,'-m','mycc',str(src),'-o',str(out),'--dump-ir'],capture_output=True,text=True)
    assert p.returncode==0 and out.exists() and 'CONST32' in p.stdout and not p.stderr
    for args,code in [([],64),(['--disable','jalr','--dump-isa'],64),(['--profile','bad','--dump-isa'],64),([str(tmp_path/'absent.c')],65),(['--doctor'],0)]:
        p=subprocess.run([sys.executable,'-m','mycc',*args],capture_output=True,text=True)
        assert p.returncode==code


def test_file_scope_statement_names_the_real_problem():
    """A statement outside any function must not read as a broken type."""
    r=compile_text('int a;\na++;\n')
    assert not r.success
    messages=[d.message for d in r.diagnostics if d.code=='E-PARSE-FILE-SCOPE']
    assert messages, 'expected E-PARSE-FILE-SCOPE, got '+', '.join(d.code for d in r.diagnostics)
    assert 'file scope' in messages[0] and "'a'" in messages[0]


def test_infinite_self_recursion_is_reported_but_not_fatal():
    """Every path calling itself again is a warning: the artifact is still emitted."""
    r=compile_text('int k(int n){ if(n<=100){} return k(n); }\nint main(void){ return k(1); }')
    codes={d.code for d in r.diagnostics}
    assert 'W-SEMA-INFINITE-RECURSION' in codes
    assert any(d.severity=='warning' for d in r.diagnostics if d.code=='W-SEMA-INFINITE-RECURSION')
    assert r.success and r.asm


@pytest.mark.parametrize('source',[
    'int fact(int n){ if(n<=1) return 1; return n*fact(n-1); }\nint main(void){ return fact(5); }',
    'int fib(int n){ if(n<2) return n; return fib(n-1)+fib(n-2); }\nint main(void){ return fib(7); }',
    'int g(int n){ if(n<=0) return 0; return g(n-1); }\nint main(void){ return g(3); }',
    'int f(void){ return 0; }\nint main(void){ return f(); }',
])
def test_terminating_recursion_is_not_flagged(source):
    """A base case, or a non-recursive exit path, must keep the warning quiet."""
    r=compile_text(source)
    assert r.success
    assert not [d for d in r.diagnostics if d.code=='W-SEMA-INFINITE-RECURSION']


def test_cli_invalid_utf8(tmp_path):
    src=tmp_path/'bad.c'; src.write_bytes(b'\xff')
    p=subprocess.run([sys.executable,'-m','mycc',str(src)],capture_output=True,text=True)
    assert p.returncode==65 and 'UTF-8' in p.stderr


def test_rars_output_uses_only_rars_directives():
    """`--rars` must hand the simulator a file it actually accepts.

    RARS rejects `.section .text` outright and has no linker, so the rewrite has to
    remove the GNU-only directives and supply the entry wrapper and I/O shims.
    """
    from mycc.rars import convert
    r=compile_text('int g;\nint main(void){ g = 3*7; printint(g); putchar(10); return 0; }')
    text=convert(r.asm)
    for banned in ('.section','.balign','.zero','.type ','.size ','.option'):
        assert banned not in text, 'RARS rejects '+banned
    assert '.text' in text and '.data' in text
    assert 'jal ra,__mycc_main' in text and 'addi a7,zero,10' in text
    assert 'putchar:' in text and 'printint:' in text
    assert '__mulsi3:' in text, 'the software multiply helper must be inlined'


def test_rars_only_emits_the_shims_a_program_uses():
    from mycc.rars import convert
    r=compile_text('int main(void){ return 0; }')
    text=convert(r.asm,runtime=False)
    assert 'jal ra,__mycc_main' in text
    for unused in ('putchar:','printint:','printhex:','exit:'):
        assert unused not in text


DETERMINISM_SOURCE='''
int acc;
int square(int n){ return n*n; }
int mix(int a,int b){ return (a^b)+(a/b)+(a%b); }
int main(void){
  int i; int total;
  total=0;
  for(i=0;i<6;i=i+1){ acc=square(i); total=total+acc+mix(i,3); }
  return total;
}
'''


def test_three_builds_are_byte_identical():
    """Three fresh compilations of one source must agree byte for byte.

    Covers the determinism requirement: no timestamps, no dict/set iteration
    order, no address-derived labels leaking into the artifact.
    """
    runs=[compile_text(DETERMINISM_SOURCE).asm for _ in range(3)]
    assert runs[0]==runs[1]==runs[2]
    assert runs[0].endswith('\n') and '\r' not in runs[0]


@pytest.mark.parametrize('profile',['PF-01','PF-03','PF-05','PF-07'])
def test_artifact_identity_is_pinned_by_capability_fingerprint(profile):
    """Same source, different capability sets: the fingerprint identifies the set.

    The fingerprint is the cheap identity check; the artifact hash proves the
    mapping fingerprint -> artifact is stable across repeated runs.
    """
    import hashlib
    p=core.load_profile(profile)
    assert len(p.fingerprint)==64
    first=hashlib.sha256(compile_text(DETERMINISM_SOURCE,profile).asm.encode()).hexdigest()
    for _ in range(2):
        assert hashlib.sha256(compile_text(DETERMINISM_SOURCE,profile).asm.encode()).hexdigest()==first


def test_lowering_report_carries_position_and_cost_premium():
    """Every fallback decision must be locatable in source and costed."""
    report=compile_text(DETERMINISM_SOURCE).lowering
    mul=[r for r in report if r.op=='MUL']
    assert mul, 'the sample must exercise multiplication'
    for rec in mul:
        assert rec.line>=1 and rec.col>=1, 'a fallback without a source position is not reviewable'
        assert rec.delta>=0
    software=[r for r in mul if 'software' in r.reason]
    assert software and all(r.delta>0 for r in software)
    assert any('missing mul' in x for r in software for x in r.rejected)


def test_hardware_rule_reports_zero_premium():
    """When the capability is present the premium must be zero and nothing is rejected."""
    report=compile_text(DETERMINISM_SOURCE,enable=['mul']).lowering
    mul=[r for r in report if r.op=='MUL']
    assert mul and all(r.delta==0 and not r.rejected for r in mul)
