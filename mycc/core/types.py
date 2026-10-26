"""Leaf types, diagnostics, AST, and target-independent constant semantics."""
from dataclasses import dataclass, field
from typing import Protocol


def i32(x):
    return ((x + 0x80000000) & 0xffffffff) - 0x80000000


def div32(a, b):
    if b == 0:
        return -1
    return i32((abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1))


@dataclass(frozen=True)
class SourceFile:
    text: str
    path: str = "<input>"

    def __post_init__(self):
        object.__setattr__(self, "text", self.text.lstrip('\ufeff').replace('\r\n', '\n'))


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    file: str
    line: int
    col: int
    value: int = 0


@dataclass(frozen=True)
class Diagnostic:
    file: str
    line: int
    col: int
    code: str
    message: str
    stage: str
    severity: str = "error"
    end_col: int = 0
    note: str = ""


class Reporter(Protocol):
    def report(self, d: Diagnostic) -> None: ...
    def has_error(self) -> bool: ...
    def error_count(self) -> int: ...


class MemoryReporter:
    def __init__(self):
        self.diagnostics = []

    def report(self, d):
        if self.error_count() < 20:
            self.diagnostics.append(d)

    def error_count(self):
        return sum(d.severity == "error" for d in self.diagnostics)

    def has_error(self):
        return self.error_count() > 0


class CompileError(Exception):
    pass


class ProfileError(Exception):
    def __init__(self, message, exit_code=65, code="E-PROFILE-INVALID"):
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code



def fail(reporter, token, stage, code, message, note=""):
    reporter.report(Diagnostic(token.file, token.line, token.col, code, message,
                               stage, end_col=token.col + max(1, len(token.text)), note=note))
    raise CompileError(message)


@dataclass(frozen=True)
class CType:
    kind: str = "int"
    length: int = 0

    @property
    def size(self):
        return self.length * 4 if self.kind == "array" else 4

    @property
    def pointer(self):
        return self.kind in ("ptr", "array")


INT = CType()
PTR = CType("ptr")
VOID = CType("void")


@dataclass
class Node:
    kind: str
    token: Token
    children: list = field(default_factory=list)
    value: object = None
    type: CType = INT
    symbol: object = None


def constant(n):
    if n.kind == "num":
        return i32(n.value)
    if n.kind == "sizeof":
        return n.value if n.value is not None else n.children[0].type.size
    if n.kind == "unary":
        a = constant(n.children[0])
        return {"+": lambda: a, "-": lambda: i32(-a), "~": lambda: i32(~a),
                "!": lambda: int(not a)}[n.value]()
    if n.kind == "binary":
        a = constant(n.children[0])
        if n.value == "&&" and not a: return 0
        if n.value == "||" and a: return 1
        b = constant(n.children[1])
        if n.value in ("/", "%") and not b:
            raise ValueError("division by zero in constant expression")
        ops = {"+": lambda: a+b, "-": lambda: a-b, "*": lambda: a*b,
               "/": lambda: div32(a,b), "%": lambda: a-div32(a,b)*b,
               "<<": lambda: a << (b & 31), ">>": lambda: a >> (b & 31),
               "&": lambda: a&b, "|": lambda: a|b, "^": lambda: a^b,
               "<": lambda: a<b, ">": lambda: a>b, "<=": lambda: a<=b,
               ">=": lambda: a>=b, "==": lambda: a==b, "!=": lambda: a!=b,
               "&&": lambda: bool(a and b), "||": lambda: bool(a or b)}
        return i32(int(ops[n.value]()))
    raise ValueError("expected an integer constant expression")


@dataclass(frozen=True)
class CodegenPolicy:
    """Environment-neutral hooks populated by an external runtime adapter."""
    name: str = 'generic'
    globals_in_bss: bool = False
    initializer: str = ''
    data_address_bits: int = 0
    stack_guard_symbol: str = ''
    stack_guard_margin: int = 0
    stack_guard_trap: str = ''

    def __post_init__(self):
        if not 0<=self.data_address_bits<=12:
            raise ValueError('bounded data addresses must fit the low 12-bit relocation')
        if self.globals_in_bss and not self.initializer:
            raise ValueError('BSS initialization policy needs an initializer symbol')
        if self.stack_guard_symbol and (not self.stack_guard_trap or not self.data_address_bits):
            raise ValueError('stack guard needs a bounded address policy and trap symbol')
        if not 0<=self.stack_guard_margin<=2047:
            raise ValueError('stack guard margin must fit a signed I immediate')


@dataclass
class CompileOptions:
    cancelled: object = None
    require_main: bool = True
    target: str = 'generic'
    policy: CodegenPolicy = field(default_factory=CodegenPolicy)
    externals: dict = field(default_factory=dict)


@dataclass
class CompileResult:
    source: object = None
    asm: str = ""
    diagnostics: list = field(default_factory=list)
    stages_ms: dict = field(default_factory=dict)
    lowering: list = field(default_factory=list)
    ir_text: str = ""
    tokens_text: str = ""
    ast_text: str = ""
    cancelled: bool = False

    @property
    def success(self):
        return not self.cancelled and not any(d.severity == "error" for d in self.diagnostics)
