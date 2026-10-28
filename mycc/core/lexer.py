"""Profile-independent UTF-8 tokenization with precise source positions."""
import re
from .types import Token, fail

KEYWORDS = set("int void if else while for return break continue sizeof".split())
UNSUPPORTED = set("char short long unsigned struct union enum typedef switch case default goto do double float const static extern volatile signed".split())
PATTERN = re.compile(r"(?P<space>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<string>\"(?:\\.|[^\"\\\n])*\")|(?P<char>'(?:\\.|[^'\\\n])*')|(?P<number>0[xX][0-9a-fA-F]+|[0-9]+)|(?P<id>[A-Za-z_][A-Za-z0-9_]*)|(?P<op><<=|>>=|\+\+|--|==|!=|<=|>=|&&|\|\||<<|>>|[+*/%&|^\-]=|[+\-*/%~!&|^<>=()\[\]{};,?:])")
ESCAPES = {'n':10, 't':9, 'r':13, '0':0, '\\':92, "'":39, '"':34}


def decode_escapes(body, token, reporter):
    """Turn the inside of a literal into character codes.

    A string is an `int` array on this target: there is no byte type, and both the
    stack frame and the TTY read 32-bit units. Keeping one code per word also keeps
    indexing uniform with hand-written `int` arrays.
    """
    codes = []
    index = 0
    while index < len(body):
        ch = body[index]
        if ch == '\\':
            nxt = body[index+1] if index + 1 < len(body) else ''
            if nxt not in ESCAPES:
                fail(reporter, token, "lex", "E-LEX-INVALID-ESCAPE",
                     f"unsupported escape sequence '\\{nxt}'",
                     "supported escapes are \\n \\t \\r \\0 \\\\ \\' and \\\"")
            codes.append(ESCAPES[nxt])
            index += 2
            continue
        if ord(ch) > 255:
            fail(reporter, token, "lex", "E-LEX-NON-ASCII-STRING",
                 "string literals may only contain characters below U+0100",
                 "the classroom TTY decodes 7-bit ASCII, so use ASCII text")
        codes.append(ord(ch))
        index += 1
    return codes


def tokenize(src, reporter):
    text = src.text
    result = []
    pos, line, col = 0, 1, 1
    while pos < len(text):
        token = Token("", text[pos], src.path, line, col)
        if text.startswith('/*', pos) and text.find('*/', pos+2) == -1:
            fail(reporter, token, "lex", "E-LEX-UNCLOSED-COMMENT", "unterminated block comment", "add '*/'")
        if text[pos] == '#':
            fail(reporter, token, "lex", "E-UNSUPPORTED-CONSTRUCT",
                 "preprocessor directive is not supported by this compiler",
                 "remove the '#' line; this compiler has a single translation unit")
        if text[pos] == '"' and text.find('"', pos+1) == -1:
            fail(reporter, token, "lex", "E-LEX-UNCLOSED-STRING", "unterminated string literal",
                 'add the closing \'"\'')
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
        elif kind == 'string':
            value = decode_escapes(raw[1:-1], token, reporter)
            kind = 'str'
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
