"""Pure compiler API and shared textual renderers."""
from time import perf_counter
from .types import (SourceFile, CompileOptions, CompileResult, CompileError, Diagnostic,
                    MemoryReporter, ProfileError, Reporter)
from .isa import ISAProfile, load_profile, check_feasible, check_target, dump_isa, dump_isa_whitelist
from .lexer import tokenize
from .parser import parse
from .sema import analyze
from .codegen import generate, lower_assembly


def format_diagnostic(d):
    return f'{d.file}:{d.line}:{d.col}: {d.severity}: {d.message}\n'+(f'note: {d.note}\n' if d.note else '')


def format_with_caret(d,src):
    header=f'{d.file}:{d.line}:{d.col}: {d.severity}: {d.message}\n'
    lines=src.text.split('\n')
    if 0 < d.line <= len(lines):
        line=lines[d.line-1]
        prefix=line[:d.col-1].expandtabs(4)
        width=max(1,len(line[d.col-1:max(d.col,d.end_col)-1].expandtabs(4)))
        header+=line.expandtabs(4)+'\n'+' '*len(prefix)+'^'+'~'*(width-1)+'\n'
    return header+(f'note: {d.note}\n' if d.note else '')


def ast_text(n,level=0):
    value=n.value if not isinstance(n.value,dict) else n.value['name']
    return ('  '*level+f'{n.kind} {value if value is not None else ""} @{n.token.line}:{n.token.col} : {n.type.kind}\n'
            +''.join(ast_text(c,level+1) for c in n.children))


def compile(src,profile=None,reporter=None,options=None):
    options=options or CompileOptions()
    profile=profile or load_profile('cpu21' if options.target=='cpu21' else 'PF-01')
    check_feasible(profile)
    reporter=reporter or MemoryReporter()
    check_target(profile,options.target)
    result=CompileResult(source=src)
    collected=MemoryReporter()

    class Tee:
        def report(self,d):
            if collected.error_count()<20:
                collected.report(d); reporter.report(d)
        def has_error(self): return collected.has_error()
        def error_count(self): return collected.error_count()
    r=Tee()
    def stage(name,fn):
        if options.cancelled and options.cancelled():
            result.cancelled=True
            raise CompileError('cancelled')
        start=perf_counter()
        try: return fn()
        finally: result.stages_ms[name]=(perf_counter()-start)*1000
    try:
        if len(src.text.encode('utf-8'))>128*1024:
            r.report(Diagnostic(src.path,1,1,'E-SOURCE-SIZE','source exceeds 128 KiB','lex',note='split the program into smaller examples'))
            raise CompileError('source size')
        tokens=stage('lex',lambda:tokenize(src,r))
        result.tokens_text=''.join(f'{t.line}:{t.col}\t{t.kind}\t{t.text}\n' for t in tokens)
        prog=stage('parse',lambda:parse(tokens,r))
        if r.has_error(): raise CompileError('parse errors')
        prog=stage('sema',lambda:analyze(prog,r,options.require_main))
        result.ast_text=ast_text(prog)
        if not r.has_error(): result.asm,result.lowering,result.ir_text=stage('codegen',lambda:generate(prog,profile,options))
    except CompileError:
        pass
    except RecursionError:
        r.report(Diagnostic(src.path,1,1,'E-PARSE-NESTING-LIMIT','nesting exceeds compiler limit','parse',note='reduce expression or block nesting'))
    result.diagnostics=collected.diagnostics
    if options.cancelled and options.cancelled(): result.cancelled=True
    if r.has_error() or result.cancelled: result.asm=''
    return result


def dump_tokens(result): return result.tokens_text
def dump_ast(result): return result.ast_text
def dump_ir(result): return result.ir_text
def dump_lowering_report(result):
    return ''.join(f'{i}\t{op}: {reason}\n'+''.join(f'  rejected: {x}\n' for x in rejected)
                   for i,(op,reason,rejected) in enumerate(result.lowering))
