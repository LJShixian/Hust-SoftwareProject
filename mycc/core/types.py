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


@dataclass(frozen=True)
class BoardAddresses:
    uart_tx: int = 0x10000000
    vga_base: int = 0x20000000
    exit_status: int = 0x10000004

    @classmethod
    def from_mapping(cls,data):
        keys={'uart_tx','vga_base','exit_status'}
        if not isinstance(data,dict) or set(data)!=keys:
            raise ValueError('MMIO configuration requires uart_tx, vga_base, exit_status')
        values={}
        for key,value in data.items():
            try: value=int(str(value),0)
            except (TypeError,ValueError): raise ValueError(f'{key}: enter a hexadecimal 0x... or decimal address')
            if not 0<=value<=0xfffffffc or value%4:
                raise ValueError(f'{key}: address must be 32-bit and 4-byte aligned')
            values[key]=value
        return cls(**values)

    def as_dict(self):
        return {'uart_tx':self.uart_tx,'vga_base':self.vga_base,'exit_status':self.exit_status}


@dataclass(frozen=True)
class CPU21Board:
    led: int = 0x1000
    seg: int = 0x1004
    vga_base: int = 0x2000
    display_ctrl: int = 0x1140
    display_cursor: int = 0x1144
    mouse_ctrl: int = 0x110c

    def as_dict(self):
        return {name:getattr(self,name) for name in self.__dataclass_fields__}

    @classmethod
    def from_mapping(cls,data):
        if not isinstance(data,dict) or set(data)!=set(cls.__dataclass_fields__):
            raise ValueError('CPU21 MMIO requires led, seg, vga_base, display_ctrl, display_cursor, mouse_ctrl; UART is unavailable')
        values={}
        for name,raw in data.items():
            try: value=int(str(raw),0)
            except (ValueError,TypeError): raise ValueError(f'{name}: enter a hexadecimal or decimal address')
            if value%4 or not 0x1000<=value<0x8000:
                raise ValueError(f'{name}: CPU21 MMIO must be aligned and within 0x1000..0x7FFC')
            values[name]=value
        if values['vga_base']+2400>0x8000:
            raise ValueError('VGA buffer exceeds the CPU21 low-address MMIO range')
        if len(set(values.values()))!=len(values):
            raise ValueError('CPU21 MMIO registers must have distinct addresses')
        if any(values['vga_base']<=value<values['vga_base']+2400 for name,value in values.items() if name!='vga_base'):
            raise ValueError('CPU21 control registers overlap the VGA framebuffer')
        return cls(**values)


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


@dataclass
class CompileOptions:
    cancelled: object = None
    require_main: bool = True
    target: str = 'generic'


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
