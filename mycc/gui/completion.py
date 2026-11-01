"""Symbol collection for the editor's code-completion popup (Qt-free)."""
import re

from ..core.lexer import tokenize
from ..core.types import MemoryReporter, SourceFile


KEYWORDS = (
    'int', 'void', 'if', 'else', 'while', 'for', 'return', 'break', 'continue', 'sizeof',
)
BUILTINS = (
    'printint', 'printhex', 'printstr', 'readint', 'readchar', 'putchar', 'getchar',
    'exit', 'printf', 'scanf', 'memcpy', 'memset',
)
FALLBACK_ID = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def collect_symbols(text):
    """Return keywords, runtime helpers and every identifier in `text`.

    Every identifier is intentionally offered: in this C subset a name is either a
    variable, a function, a parameter or a labels-free symbol, and all four are
    useful completions. Comments and literals are excluded by the lexer; if the
    file is temporarily incomplete, a regex fallback keeps suggestions useful.
    """
    words = set(KEYWORDS) | set(BUILTINS)
    try:
        reporter = MemoryReporter()
        tokens = tokenize(SourceFile(text, '<completion>'), reporter)
        words.update(token.text for token in tokens if token.kind == 'id')
    except Exception:
        words.update(FALLBACK_ID.findall(text))
    return sorted(words, key=lambda word: (word.lower(), word))
