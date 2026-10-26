from mycc import core


def test_multiple_semantic_errors():
    r=core.compile(core.SourceFile('int main(){a=1; b=2; c=3;return 0;}'))
    assert len(r.diagnostics)==3 and not r.asm
    assert all(d.code=='E-SEMA-UNDECLARED-ID' for d in r.diagnostics)


def test_error_cap():
    r=core.compile(core.SourceFile('int main(){'+'missing=1;'*50+'return 0;}'))
    assert len(r.diagnostics)==20 and not r.asm


def test_parse_statement_recovery():
    r=core.compile(core.SourceFile('int main(){int a=; int b=; return 0;}'))
    assert len(r.diagnostics)==2 and not r.asm


def test_void_and_pointer_types():
    for source in ['int main(){int x;int* p;p=&x;*p=5;return !p;}',
                   'int main(){int x;int* p=&x;return 1+p-p;}',
                   'void f(){return;} int main(){f();return 0;}']:
        r=core.compile(core.SourceFile(source)); assert r.success, r.diagnostics
    for source in ['int main(){int* p;return ~p;}',
                   'int main(){int* p;int* q;return p+q;}',
                   'int main(){int x;int* p=&x;int* q=&p;return 0;}',
                   'void f(){return;} int main(){if(f()) return 1;return 0;}',
                   'int main(){return;}']:
        assert not core.compile(core.SourceFile(source)).success


def test_constant_semantics():
    from mycc.core.types import constant
    from mycc.core.lexer import tokenize
    from mycc.core.parser import Parser
    for expr,value in [('1+2*3',7),('!0',1),('~0',-1),('4>>1',2),('0&&(1/0)',0),('1||(1/0)',1),('sizeof(int*)',4)]:
        reporter=core.MemoryReporter()
        n=Parser(tokenize(core.SourceFile(expr),reporter),reporter).expr()
        assert constant(n)==value
