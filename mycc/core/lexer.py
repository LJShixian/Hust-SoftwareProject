"""Profile-independent UTF-8 tokenization with precise source positions."""
import re
from .types import Token, fail

KEYWORDS = set("int void if else while for return break continue sizeof".split())
UNSUPPORTED = set("char short long unsigned struct union enum typedef switch case default goto do double float const static extern volatile signed".split())
PATTERN = re.compile(r"(?P<space>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<char>'(?:\\.|[^'\\\n])*')|(?P<number>0[xX][0-9a-fA-F]+|[0-9]+)|(?P<id>[A-Za-z_][A-Za-z0-9_]*)|(?P<op><<=|>>=|\+\+|--|==|!=|<=|>=|&&|\|\||<<|>>|[+*/%&|^\-]=|[+\-*/%~!&|^<>=()\[\]{};,?:])")
ESCAPES = {'n':10, 't':9, 'r':13, '0':0, '\\':92, "'":39, '"':34}


def tokenize(src, reporter):
    text = src.text
    result = []
    pos, line, col = 0, 1, 1
    while pos < len(text):
        token = Token("", text[pos], src.path, line, col)
        if text.startswith('/*', pos) and text.find('*/', pos+2) == -1:
            fail(reporter, token, "lex", "E-LEX-UNCLOSED-COMMENT", "unterminated block comment", "add '*/'")
        if text[pos] in '#"':
            feature = "preprocessor directive" if text[pos] == '#' else "string literal"
            fail(reporter, token, "lex", "E-UNSUPPORTED-CONSTRUCT", feature + " is not supported by this compiler", "use int arrays and character literals")
        match = PATTERN.match(text, pos)
        if not match:
            fail(reporter, token, "lex", "E-LEX-UNEXPECTED-CHAR", f"unexpected character U+{ord(text[pos]):04X}", "remove this character")
        kind, raw = match.lastgroup, match.group()
        value = 0
        if kind == 'id':
            if len(raw) > 255:
                fail(reporter, token, "lex", "E-LEX-IDENTIFIER-LENGTH", "identifier exceeds 255 characters")
            kind = raw if raw in KEYWORDS else 'unsupported' if raw in UNSUPPORTED else 'id'
        elif kind == 'number':
            try:
                base = 16 if raw.lower().startswith('0x') else 8 if raw.startswith('0') else 10
                value = int(raw, base)
            except ValueError:
                fail(reporter, token, "lex", "E-LEX-INVALID-INTEGER", f"invalid integer literal {raw!r}")
            limit = 0xffffffff if base == 16 else 0x7fffffff
            if value > limit:
                fail(reporter, token, "lex", "E-LEX-INTEGER-RANGE", "integer literal out of 32-bit range")
            kind = 'num'
        elif kind == 'char':
            body = raw[1:-1]
            if len(body) == 1:
                value = ord(body)
            elif len(body) == 2 and body[0] == '\\' and body[1] in ESCAPES:
                value = ESCAPES[body[1]]
            else:
                fail(reporter, token, "lex", "E-LEX-INVALID-CHAR", "expected one character or a supported escape")
            kind = 'num'
        elif kind == 'op':
            kind = raw
        if kind not in ('space', 'comment'):
            result.append(Token(kind, raw, src.path, line, col, value))
        count = raw.count('\n')
        line += count
        col = len(raw.rsplit('\n',1)[-1]) + 1 if count else col + len(raw)
        pos = match.end()
    result.append(Token('eof', '', src.path, line, col))
    return result
