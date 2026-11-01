"""Deterministic C-subset formatting used by the editor's Format command.

This is deliberately a *source-preserving* formatter: it never rewrites string
or character literals and never changes comment text. It normalises indentation,
trim-safe punctuation spacing, blank lines and the final newline; it does not
reflow one-line function bodies (the editor's auto-indent handles new lines).
"""
import re


def _literal_end(text, index, quote):
    index += 1
    while index < len(text):
        ch = text[index]
        if ch == '\\':
            index += 2
            continue
        if ch == quote:
            return index + 1
        index += 1
    return len(text)


def _split_line(line, in_block):
    """Split one line into ('code'|'literal'|'comment', text) segments.

    `in_block` is the block-comment state on entry and is returned for the next
    line. Comments and literals are kept verbatim; only code segments are passed
    through the spacing normaliser.
    """
    segments = []
    code = []
    index = 0
    while index < len(line):
        if in_block:
            end = line.find('*/', index)
            if end < 0:
                segments.append(('comment', line[index:]))
                return segments, True
            segments.append(('comment', line[index:end + 2]))
            index = end + 2
            in_block = False
            continue
        if line.startswith('//', index):
            if code:
                segments.append(('code', ''.join(code)))
                code = []
            segments.append(('comment', line[index:]))
            return segments, in_block
        if line.startswith('/*', index):
            if code:
                segments.append(('code', ''.join(code)))
                code = []
            end = line.find('*/', index + 2)
            if end < 0:
                segments.append(('comment', line[index:]))
                return segments, True
            segments.append(('comment', line[index:end + 2]))
            index = end + 2
            continue
        ch = line[index]
        if ch in '"\'':
            if code:
                segments.append(('code', ''.join(code)))
                code = []
            end = _literal_end(line, index, ch)
            segments.append(('literal', line[index:end]))
            index = end
            continue
        code.append(ch)
        index += 1
    if code:
        segments.append(('code', ''.join(code)))
    return segments, in_block


def _normalize_code(text):
    """Whitespace-only cleanup for a code segment (never called on literals)."""
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\s+([,;\)\]\}])', r'\1', text)
    text = re.sub(r'([,;])(?=\S)', r'\1 ', text)
    text = re.sub(r'(?<=[\(\[])\s+', '', text)
    text = re.sub(r'\s+(?=[\)\]])', '', text)
    text = re.sub(r'\b(if|while|for)\s*\(', r'\1 (', text)
    text = re.sub(r'(?<=\S)\s*\{\s*', ' { ', text)
    text = re.sub(r'\}\s*else\b', '} else', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _join(segments):
    out = ''
    for kind, text in segments:
        if kind == 'code':
            text = _normalize_code(text)
            if not text:
                continue
            if (out and out[-1] not in ' \t' and not out.endswith(('(', '[', '{'))
                    and (text[0].isalnum() or text[0] in '+-*/%&|^<>=!?')):
                out += ' '
            out += text
        elif kind == 'comment':
            if out and out[-1] not in ' \t':
                out += ' '
            out += text
        else:
            out += text
    return out.strip()


def _reflow_line(line):
    """Split a compact line at top-level `{`, `}`, `;` (never inside literals).

    One-line functions such as `int main(){return 0;}` are common in teaching
    snippets.  Brace initialisers (`= {1, 2}`) and lines containing string/comment
    content are deliberately left alone: changing whitespace there is safe, but
    moving their punctuation across lines is not.
    """
    if any(marker in line for marker in ('//', '/*', '"', "'")):
        return [line]
    if re.search(r'=\s*\{', line):
        return [line]
    if '{' not in line and '}' not in line and ';' not in line:
        return [line]
    parts = []
    current = []
    paren = 0
    for ch in line:
        if ch == '{':
            if paren == 0:
                current.append(ch)
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        elif ch == '}':
            if paren == 0:
                if ''.join(current).strip():
                    parts.append(''.join(current).strip())
                    current = []
                current.append(ch)
            else:
                paren = max(0, paren - 1)
                current.append(ch)
        elif ch == ';':
            current.append(ch)
            if paren == 0:
                parts.append(''.join(current).strip())
                current = []
        elif ch in '([':
            paren += 1
            current.append(ch)
        elif ch in ')]':
            paren = max(0, paren - 1)
            current.append(ch)
        else:
            current.append(ch)
    if ''.join(current).strip():
        parts.append(''.join(current).strip())
    return [part for part in parts if part] or [line]


def format_source(text, indent_width=4):
    """Format a whole C-subset source file; returns text ending in one newline.

    - tabs in leading indentation become spaces;
    - braces and parentheses drive one indentation level each;
    - closing delimiters dedent the line;
    - punctuation spacing is normalised outside literals/comments;
    - comments and literals are preserved byte-for-byte;
    - trailing whitespace, trailing blank lines and the final newline are fixed.
    """
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = []
    for raw in text.split('\n'):
        lines.extend(_reflow_line(raw))
    result = []
    depth = 0
    paren = 0
    in_block = False
    pending_control = 0
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            result.append('')
            continue
        segments, in_block = _split_line(line, in_block)
        code = ''.join(part for kind, part in segments if kind == 'code')
        visible = _join(segments)
        if not visible:
            result.append('')
            continue
        starts_close = visible.startswith('}')
        indent_depth = max(0, depth - 1) if starts_close else depth
        continuation = 1 if paren > 0 and not visible.startswith((')', ']', '}')) else 0
        control_body = pending_control if not starts_close and not visible.startswith('{') else 0
        result.append(' ' * (indent_width * (indent_depth + continuation + control_body)) + visible)
        current_control = bool(
            re.match(r'^(if|for|while|else)\b', visible)
            and not visible.endswith('{') and not visible.endswith(';')
        )
        pending_control = (control_body + 1) if current_control else 0
        depth = max(0, depth + code.count('{') - code.count('}'))
        paren = max(0, paren + code.count('(') + code.count('[') - code.count(')') - code.count(']'))
    while result and not result[-1].strip():
        result.pop()
    return '\n'.join(result) + '\n' if result else ''
