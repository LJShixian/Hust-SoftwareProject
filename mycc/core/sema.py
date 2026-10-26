"""Lexical scopes and type checking; intentionally knows nothing about ISA."""
from dataclasses import dataclass
from .types import INT, PTR, VOID, Diagnostic, CompileError, constant, fail


@dataclass
class Symbol:
    name: str
    type: object
    global_: bool = False
    params: object = None
    offset: int = 0
    initial: object = None


BUILTINS = {
    'putchar': (VOID, [INT]), 'printint': (VOID, [INT]), 'printhex': (VOID, [INT]),
    'exit': (VOID, [INT]), 'memcpy': (PTR, [PTR, PTR, INT]),
    'memset': (PTR, [PTR, INT, INT]),
}


class Analyzer:
    def __init__(self, reporter, externals=None):
        self.reporter = reporter
        self.builtins=BUILTINS | (externals or {})
        self.scopes = [{name: Symbol(name, ret, True, args) for name,(ret,args) in self.builtins.items()}]
        self.loop = 0
        self.function = None
        self.locals = []

    def error(self, n, message, code='E-SEMA-TYPE'):
        fail(self.reporter, n.token, 'sema', code, message, 'use int values, int pointers and matching function arguments')

    def declare(self, n, global_=False, params=None):
        if str(n.value).startswith('__mycc_'):
            self.error(n,'__mycc_ names are reserved for the runtime','E-SEMA-RESERVED-ID')
        if n.value in self.scopes[-1]: self.error(n, f"duplicate definition of '{n.value}'", 'E-SEMA-DUPLICATE-ID')
        if n.type == VOID and n.kind != 'func': self.error(n, 'variables and parameters cannot have void type')
        s = Symbol(n.value, n.type, global_, params)
        n.symbol = s
        self.scopes[-1][n.value] = s
        if not global_: self.locals.append(s)
        return s

    def lookup(self, n):
        for scope in reversed(self.scopes):
            if n.value in scope: return scope[n.value]
        self.error(n, f"undeclared identifier '{n.value}'", 'E-SEMA-UNDECLARED-ID')

    def compatible(self, typ, n):
        return (typ == INT and n.type == INT) or (typ.pointer and (n.type.pointer or (n.kind == 'num' and n.value == 0)))

    def lvalue(self, n, address=False):
        valid = n.kind in ('id','index') or (n.kind == 'unary' and n.value == '*')
        if n.symbol and n.symbol.params is not None: valid = False
        if n.type.kind == 'array' and not address: valid = False
        if not valid: self.error(n, 'operand must be a modifiable lvalue', 'E-SEMA-LVALUE')

    def expression(self, n):
        if n.kind == 'num': return INT
        if n.kind == 'id':
            n.symbol = self.lookup(n); n.type = n.symbol.type
            if n.symbol.params is not None: self.error(n, 'function identifiers can only be used in a direct call')
        elif n.kind == 'call':
            callee = n.children[0]
            if callee.kind != 'id': self.error(n, 'only direct function calls are supported')
            sym = self.lookup(callee); callee.symbol = sym; n.symbol = sym
            if sym.params is None: self.error(n, f"'{sym.name}' is not a function")
            args = n.children[1:]
            if len(args) != len(sym.params): self.error(n, f"'{sym.name}' expects {len(sym.params)} arguments, got {len(args)}", 'E-SEMA-ARGUMENTS')
            for a,t in zip(args,sym.params):
                self.expression(a)
                if not self.compatible(t,a): self.error(a, 'function argument type mismatch')
            n.type = sym.type
        elif n.kind == 'sizeof':
            if n.children: self.expression(n.children[0])
            n.value = constant(n)
            n.type = INT
        elif n.kind == 'index':
            a,b = n.children
            self.expression(a); self.expression(b)
            if not a.type.pointer or b.type != INT: self.error(n, 'array subscript requires a pointer and an int')
            n.type = INT
        elif n.kind in ('unary','postfix'):
            a = n.children[0]; self.expression(a)
            op = n.value
            if op == '&':
                self.lvalue(a, True)
                if a.type.pointer: self.error(n, 'multiple pointer levels are not supported', 'E-UNSUPPORTED-CONSTRUCT')
                n.type = PTR
            elif op == '*':
                if not a.type.pointer: self.error(n, 'dereference requires an int pointer')
                n.type = INT
            elif op in ('++','--'):
                self.lvalue(a); n.type = a.type
            elif op == '!':
                if a.type == VOID: self.error(n, 'void value cannot be tested')
                n.type = INT
            else:
                if a.type != INT: self.error(n, f"'{op}' requires an int")
                n.type = INT
        elif n.kind in ('binary','assign'):
            a,b = n.children
            self.expression(a); self.expression(b)
            op = n.value
            if n.kind == 'assign':
                self.lvalue(a)
                if op == '=':
                    if not self.compatible(a.type,b): self.error(n, 'assignment type mismatch')
                elif a.type.pointer:
                    if op not in ('+=','-=') or b.type != INT: self.error(n, 'pointer compound assignment requires += or -= int')
                elif b.type != INT: self.error(n, 'integer compound assignment requires int')
                n.type = a.type
            elif op in ('&&','||'):
                if VOID in (a.type,b.type): self.error(n, 'void value cannot be tested')
                n.type = INT
            elif op in ('==','!=','<','>','<=','>='):
                if not (self.compatible(a.type,b) or self.compatible(b.type,a)): self.error(n,'comparison type mismatch')
                n.type = INT
            elif op in ('+','-') and (a.type.pointer or b.type.pointer):
                if a.type.pointer and b.type == INT: n.type = PTR
                elif op == '+' and a.type == INT and b.type.pointer: n.type = PTR
                elif op == '-' and a.type.pointer and b.type.pointer: n.type = INT
                else: self.error(n, 'invalid pointer arithmetic')
            else:
                if a.type != INT or b.type != INT: self.error(n, f"'{op}' requires two ints")
                n.type = INT
        return n.type

    def statement(self, n, new_scope=True):
        if n.kind == 'block':
            if new_scope: self.scopes.append({})
            for child in n.children:
                try: self.statement(child)
                except CompileError:
                    if self.reporter.error_count()>=20: raise
            if new_scope: self.scopes.pop()
        elif n.kind == 'decl':
            self.declare(n)
            self.initializer(n)
        elif n.kind == 'expr': self.expression(n.children[0])
        elif n.kind == 'return':
            expected = self.function.type
            if n.children:
                self.expression(n.children[0])
                if expected == VOID or not self.compatible(expected,n.children[0]): self.error(n,'return type mismatch')
            elif expected != VOID: self.error(n, 'int function requires a return value')
        elif n.kind in ('break','continue'):
            if not self.loop: self.error(n, f"'{n.kind}' must be inside a loop", 'E-SEMA-LOOP-CONTROL')
        elif n.kind == 'if':
            if self.expression(n.children[0]) == VOID: self.error(n,'condition cannot be void')
            for child in n.children[1:]: self.statement(child)
        elif n.kind in ('while','for'):
            self.scopes.append({}); self.loop += 1
            if n.kind == 'for':
                init,cond,step,body = n.children
                self.statement(init) if init.kind == 'decl' else self.expression(init)
                if self.expression(cond) == VOID: self.error(cond, 'condition cannot be void')
                self.expression(step)
            else:
                cond,body = n.children
                if self.expression(cond) == VOID: self.error(cond, 'condition cannot be void')
            self.statement(body)
            self.loop -= 1; self.scopes.pop()

    def initializer(self,n,global_=False):
        if n.type.kind == 'array' and len(n.children) > n.type.length: self.error(n,'too many array initializers')
        if n.type.kind != 'array' and len(n.children)>1: self.error(n,'too many scalar initializers')
        for child in n.children:
            self.expression(child)
            if not self.compatible(INT if n.type.kind == 'array' else n.type,child): self.error(child,'initializer type mismatch')
        if global_:
            try: n.symbol.initial = [constant(x) for x in n.children]
            except (ValueError,KeyError) as exc: self.error(n,str(exc),'E-SEMA-CONSTANT')

    def program(self, prog, require_main=True):
        defined=set()
        for n in prog.children:
            if n.kind=='func' and n.value in self.builtins and n.value not in defined:
                ret,args=self.builtins[n.value]
                if n.type!=ret or [p.type for p in n.children[:-1]]!=args:
                    self.error(n,'runtime function signature mismatch')
                self.scopes[0].pop(n.value)
            defined.add(n.value)
            self.declare(n,True,[p.type for p in n.children[:-1]] if n.kind == 'func' else None)
        main = self.scopes[0].get('main')
        if require_main and (not main or main.params != [] or main.type != INT):
            self.error(prog,'program must define int main(void)', 'E-SEMA-MAIN')
        for n in prog.children:
            if n.kind == 'decl': self.initializer(n,True); continue
            self.function = n; self.locals = []; self.scopes.append({})
            for p in n.children[:-1]: self.declare(p)
            self.statement(n.children[-1],False)
            n.value = {'name':n.symbol.name,'locals':list(self.locals)}
            self.scopes.pop()
            if n.type != VOID and not self.returns(n.children[-1]):
                t=n.token
                self.reporter.report(Diagnostic(t.file,t.line,t.col,'W-SEMA-MISSING-RETURN',
                    'control may reach end of non-void function','sema','warning',note='add a return statement'))
        return prog

    def returns(self,n):
        if n.kind == 'return': return True
        if n.kind == 'block': return any(self.returns(x) for x in n.children)
        if n.kind == 'if' and len(n.children)==3: return all(self.returns(x) for x in n.children[1:])
        return False


def analyze(prog,reporter,require_main=True,externals=None):
    return Analyzer(reporter,externals).program(prog,require_main)
