"""Recursive descent declarations/statements and precedence climbing expressions."""
from .types import Node, CType, INT, PTR, VOID, CompileError, constant, fail

PRECEDENCE = {}
for level, group in enumerate(["= += -= *= /= %= &= |= ^= <<= >>=", "||", "&&", "|", "^", "&", "== !=", "< <= > >=", "<< >>", "+ -", "* / %"], 1):
    PRECEDENCE.update({op: level for op in group.split()})


class Parser:
    def __init__(self, tokens, reporter):
        self.tokens, self.reporter, self.pos = tokens, reporter, 0
        self.depth = 0
        self.blocks = 0

    @property
    def t(self):
        return self.tokens[self.pos]

    def error(self, message, code="E-PARSE-EXPECTED-TOKEN", note=None):
        fail(self.reporter, self.t, 'parse', code, message,
             note or "check the C subset grammar in README.md")

    def take(self, kind=None):
        t = self.t
        if t.kind == 'unsupported' or t.kind in ('?', ':'):
            self.error(f"'{t.text}' is not supported by this compiler (use int, if or while)", "E-UNSUPPORTED-CONSTRUCT")
        if kind is not None and t.kind != kind:
            self.error(f"expected {kind!r}, got {t.text!r}")
        self.pos += 1
        return t

    def accept(self, kind):
        if self.t.kind == kind:
            return self.take()
        return None

    def typename(self):
        t = self.take()
        if t.kind not in ('int', 'void'):
            self.error("expected 'int' or 'void'")
        typ = VOID if t.kind == 'void' else INT
        if self.accept('*'):
            if typ == VOID: self.error("void pointers are not supported", "E-UNSUPPORTED-CONSTRUCT")
            typ = PTR
        return typ

    def decl(self, typ, name, parameter=False):
        if self.accept('['):
            if parameter:
                self.take(']')
                typ = PTR
            else:
                size = self.expr()
                self.take(']')
                try:
                    length = constant(size)
                    if not 0 < length <= 32768: raise ValueError("array length must be in 1..32768")
                except (ValueError, KeyError) as exc:
                    self.error(str(exc), "E-SEMA-ARRAY-LENGTH")
                typ = CType('array', length)
        children = []
        if not parameter and self.accept('='):
            if self.accept('{'):
                if self.t.kind != '}':
                    children.append(self.expr())
                    while self.accept(','):
                        if self.t.kind == '}': break
                        children.append(self.expr())
                self.take('}')
            else:
                children.append(self.expr())
        return Node('decl', name, children, name.text, typ)

    def program(self):
        out = Node('program', self.t)
        while self.t.kind != 'eof':
            if self.t.kind not in ('int', 'void'):
                # A statement or expression at file scope used to surface as the
                # generic "expected 'int' or 'void'", which reads like a broken
                # type rather than "this code has to live inside a function".
                self.error(f"only declarations may appear at file scope; '{self.t.text}' begins a statement or expression",
                           'E-PARSE-FILE-SCOPE',
                           'move it inside a function body, for example int main(void) { ... }')
            typ = self.typename()
            name = self.take('id')
            if self.accept('('):
                params = []
                if self.t.kind == 'void' and self.tokens[self.pos+1].kind == ')': self.take()
                elif self.t.kind != ')':
                    while True:
                        pt = self.typename()
                        params.append(self.decl(pt, self.take('id'), True))
                        if not self.accept(','): break
                self.take(')')
                if len(params) > 8: self.error("at most 8 parameters are supported")
                body = self.stmt()
                if body.kind != 'block': self.error("function definition requires a block")
                out.children.append(Node('func', name, params+[body], name.text, typ))
            else:
                out.children.append(self.decl(typ, name))
                self.take(';')
        return out

    def stmt(self):
        t = self.t
        if self.accept('{'):
            self.blocks += 1
            if self.blocks > 100: self.error("block nesting exceeds 100", "E-PARSE-NESTING-LIMIT")
            children = []
            while self.t.kind not in ('}', 'eof'):
                start=self.pos
                try: children.append(self.stmt())
                except CompileError:
                    # Nesting failures must unwind immediately; statement errors
                    # recover at a semicolon or the enclosing closing brace.
                    if self.reporter.error_count()>=20 or self.depth>200 or self.blocks>100: raise
                    while self.t.kind not in (';','}','eof'): self.pos+=1
                    if self.t.kind==';': self.pos+=1
                    if self.pos==start and self.t.kind not in ('}','eof'): self.pos+=1
                    self.depth=0
            self.take('}')
            self.blocks -= 1
            return Node('block', t, children)
        if self.accept(';'): return Node('empty', t)
        if t.kind in ('int', 'void'):
            typ = self.typename()
            node = self.decl(typ, self.take('id'))
            self.take(';')
            return node
        if self.accept('if'):
            self.take('('); cond = self.expr(); self.take(')')
            children = [cond, self.stmt()]
            if self.accept('else'): children.append(self.stmt())
            return Node('if', t, children)
        if self.accept('while'):
            self.take('('); cond = self.expr(); self.take(')')
            return Node('while', t, [cond, self.stmt()])
        if self.accept('for'):
            self.take('(')
            init = self.stmt() if self.t.kind == 'int' else self.optional_expr(';')
            cond = self.optional_expr(';', 1)
            step = self.optional_expr(')')
            return Node('for', t, [init, cond, step, self.stmt()])
        if self.accept('return'):
            children = [] if self.t.kind == ';' else [self.expr()]
            self.take(';')
            return Node('return', t, children)
        if t.kind in ('break', 'continue'):
            self.take(); self.take(';')
            return Node(t.kind, t)
        n = self.expr(); self.take(';')
        return Node('expr', t, [n])

    def optional_expr(self, end, default=0):
        n = Node('num', self.t, value=default) if self.t.kind == end else self.expr()
        self.take(end)
        return n

    def expr(self, minimum=1):
        self.depth += 1
        if self.depth > 200: self.error("expression nesting exceeds 200", "E-PARSE-NESTING-LIMIT")
        left = self.unary()
        while PRECEDENCE.get(self.t.kind, 0) >= minimum:
            op = self.take()
            prec = PRECEDENCE[op.kind]
            right = self.expr(prec if prec == 1 else prec+1)
            left = Node('assign' if prec == 1 else 'binary', op, [left,right], op.kind)
        self.depth -= 1
        return left

    def unary(self):
        t = self.t
        if t.kind in ('+', '-', '!', '~', '*', '&', '++', '--'):
            self.take()
            self.depth += 1
            if self.depth > 200: self.error("expression nesting exceeds 200", "E-PARSE-NESTING-LIMIT")
            child = self.unary()
            self.depth -= 1
            return Node('unary', t, [child], t.kind)
        if self.accept('sizeof'):
            self.take('(')
            if self.t.kind == 'int':
                typ = self.typename(); self.take(')')
                return Node('sizeof', t, value=typ.size)
            child = self.expr(); self.take(')')
            return Node('sizeof', t, [child])
        if self.accept('('):
            if self.t.kind in ('int','void'): self.error("casts are not supported by this compiler", "E-UNSUPPORTED-CONSTRUCT")
            n = self.expr(); self.take(')')
        elif t.kind == 'num':
            self.take(); n = Node('num', t, value=t.value)
        else:
            self.take('id'); n = Node('id', t, value=t.text)
        while True:
            if self.accept('['):
                index = self.expr(); self.take(']')
                n = Node('index', t, [n,index])
            elif self.accept('('):
                args = []
                if self.t.kind != ')':
                    args.append(self.expr())
                    while self.accept(','): args.append(self.expr())
                self.take(')'); n = Node('call', t, [n]+args)
            elif self.t.kind in ('++', '--'):
                op = self.take(); n = Node('postfix', op, [n], op.kind)
            else: break
        return n


def parse(tokens, reporter):
    return Parser(tokens, reporter).program()
