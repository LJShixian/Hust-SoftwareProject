"""VSCode-like editing helpers: auto-indent, bracket pairing, completion, format."""
import re

from PySide6.QtCore import Qt, QTimer, QStringListModel
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QCompleter, QPlainTextEdit

from .completion import collect_symbols
from .formatting import format_source


PAIRS = {'(': ')', '[': ']', '{': '}'}
CLOSES = {close: open_ for open_, close in PAIRS.items()}


class CodeEditor(QPlainTextEdit):
    """QPlainTextEdit with the editing behaviour expected from a modern IDE."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(False)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self._indent_width = 4
        self._symbols = []
        self._model = QStringListModel(self)
        self.completer = QCompleter(self)
        self.completer.setModel(self._model)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchStartsWith)
        self.completer.setMaxVisibleItems(12)
        self.completer.setWrapAround(True)
        self.completer.activated[str].connect(self.insert_completion)
        self.textChanged.connect(self.refresh_symbols)
        self.refresh_symbols()

    # ------------------------------------------------------------- completion
    def refresh_symbols(self):
        self._symbols = collect_symbols(self.toPlainText())
        self._model.setStringList(self._symbols)

    def completion_words(self):
        return list(self._symbols)

    def _current_prefix(self):
        cursor = self.textCursor()
        line = cursor.block().text()
        prefix = line[:cursor.positionInBlock()]
        match = re.search(r'[A-Za-z_][A-Za-z0-9_]*$', prefix)
        return match.group(0) if match else ''

    def _context_before_cursor(self):
        """Return (in_block_comment, in_string, in_line_comment)."""
        text = self.toPlainText()[:self.textCursor().position()]
        in_block = False
        quote = None
        line_comment = False
        index = 0
        while index < len(text):
            ch = text[index]
            if in_block:
                end = text.find('*/', index)
                if end < 0:
                    return True, False, False
                index = end + 2
                in_block = False
                continue
            if line_comment:
                if ch == '\n':
                    line_comment = False
                index += 1
                continue
            if text.startswith('//', index):
                line_comment = True
                index += 2
                continue
            if text.startswith('/*', index):
                in_block = True
                index += 2
                continue
            if quote:
                if ch == '\\':
                    index += 2
                    continue
                if ch == quote or ch == '\n':
                    quote = None
                index += 1
                continue
            if ch in '"\'':
                quote = ch
            index += 1
        return in_block, bool(quote), line_comment

    def _in_literal_or_comment(self):
        return any(self._context_before_cursor())

    def request_completion(self, force=False):
        if self._in_literal_or_comment():
            self.completer.popup().hide()
            return
        prefix = self._current_prefix()
        if not force and len(prefix) < 2:
            self.completer.popup().hide()
            return
        self.completer.setCompletionPrefix(prefix)
        if self.completer.completionCount() == 0:
            self.completer.popup().hide()
            return
        if self.completer.completionCount() == 1 and self.completer.currentCompletion() == prefix:
            self.completer.popup().hide()
            return
        rect = self.cursorRect()
        rect.setWidth(max(240, min(560, self.fontMetrics().horizontalAdvance(prefix) + 300)))
        self.completer.complete(rect)

    def insert_completion(self, text):
        cursor = self.textCursor()
        prefix = self.completer.completionPrefix()
        if prefix:
            cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, len(prefix))
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.completer.popup().hide()

    # --------------------------------------------------------------- editing
    def _next_char(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            return ''
        text = self.toPlainText()
        position = cursor.position()
        return text[position] if position < len(text) else ''

    def _insert_pair(self, opener):
        close = PAIRS.get(opener)
        if close is None or self._in_literal_or_comment():
            return False
        cursor = self.textCursor()
        if cursor.hasSelection():
            selected = cursor.selectedText()
            cursor.insertText(opener + selected + close)
            self.setTextCursor(cursor)
            return True
        next_char = self._next_char()
        if next_char == close:
            return False
        if next_char == '' or next_char in ' \t\n)]};,':
            cursor.insertText(opener + close)
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
            return True
        return False

    def _skip_closing(self, char):
        if self._next_char() != char:
            return False
        cursor = self.textCursor()
        if cursor.position() == 0:
            return False
        previous = self.toPlainText()[cursor.position() - 1]
        return CLOSES.get(char) == previous or previous in ' \t\n'

    def _remove_pair(self):
        cursor = self.textCursor()
        if cursor.hasSelection() or cursor.position() == 0:
            return False
        text = self.toPlainText()
        position = cursor.position()
        if position >= len(text):
            return False
        previous, following = text[position - 1], text[position]
        if PAIRS.get(previous) != following:
            return False
        cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        self.setTextCursor(cursor)
        return True

    def _paren_balance(self, text):
        return (text.count('(') + text.count('[')) - (text.count(')') + text.count(']'))

    def _newline_with_indent(self):
        cursor = self.textCursor()
        block = cursor.block()
        before = block.text()[:cursor.positionInBlock()]
        after = block.text()[cursor.positionInBlock():]
        leading = block.text()[:len(block.text()) - len(block.text().lstrip(' \t'))]
        base = len(leading.expandtabs(self._indent_width))
        stripped = before.rstrip()
        extra = 0
        if stripped.endswith('{') or self._paren_balance(before) > 0:
            extra = self._indent_width
        elif re.match(r'^(if|for|while|else)\b.*\)?$', stripped):
            # A brace-less if/for/while body still gets one visual level.
            extra = self._indent_width
        if after.lstrip().startswith('}'):
            if stripped.endswith('{'):
                cursor.insertText('\n' + ' ' * (base + self._indent_width) + '\n' + ' ' * base)
                cursor.movePosition(QTextCursor.Up)
                cursor.movePosition(QTextCursor.EndOfLine)
                self.setTextCursor(cursor)
                return
            extra = 0
        cursor.insertText('\n' + ' ' * (base + extra))
        self.setTextCursor(cursor)

    def _indent_line(self, block, outdent=False):
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.StartOfBlock)
        if outdent:
            text = block.text()
            remove = 0
            if text.startswith('\t'):
                remove = 1
            else:
                while remove < self._indent_width and text.startswith(' ', remove):
                    remove += 1
            if remove:
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, remove)
                cursor.removeSelectedText()
        else:
            cursor.insertText(' ' * self._indent_width)

    def _selected_blocks(self):
        cursor = self.textCursor()
        start = self.document().findBlock(cursor.selectionStart())
        end = self.document().findBlock(cursor.selectionEnd())
        return start, end

    def indent_selection(self, outdent=False):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            block = cursor.block()
            if outdent:
                self._indent_line(block, outdent=True)
            else:
                column = cursor.positionInBlock()
                spaces = self._indent_width - (column % self._indent_width)
                cursor.insertText(' ' * spaces)
                self.setTextCursor(cursor)
            return
        first, last = self._selected_blocks()
        cursor.beginEditBlock()
        block = first
        while True:
            self._indent_line(block, outdent=outdent)
            if block == last:
                break
            block = block.next()
        cursor.endEditBlock()
        # Keep a sensible selection after the positions shift.
        new_cursor = QTextCursor(self.document())
        new_cursor.setPosition(first.position())
        new_cursor.setPosition(last.position() + len(last.text()), QTextCursor.KeepAnchor)
        self.setTextCursor(new_cursor)

    def _outdent_brace_line(self):
        cursor = self.textCursor()
        block = cursor.block()
        before = block.text()[:cursor.positionInBlock()]
        if before.strip():
            return False
        leading = len(block.text()) - len(block.text().lstrip(' '))
        if leading < self._indent_width:
            return False
        select = QTextCursor(block)
        select.movePosition(QTextCursor.StartOfBlock)
        select.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, self._indent_width)
        select.removeSelectedText()
        return True

    def keyPressEvent(self, event):
        if (event.modifiers() & Qt.ControlModifier) and event.key() == Qt.Key_Space:
            self.request_completion(force=True)
            event.accept()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.completer.popup().isVisible():
                super().keyPressEvent(event)
                return
            self._newline_with_indent()
            event.accept()
            return
        if event.key() == Qt.Key_Tab:
            if self.completer.popup().isVisible():
                super().keyPressEvent(event)
                return
            self.indent_selection(outdent=bool(event.modifiers() & Qt.ShiftModifier))
            event.accept()
            return
        if event.key() == Qt.Key_Backspace and self._remove_pair():
            event.accept()
            return
        text = event.text()
        if text in (')', ']', '}'):
            if self._skip_closing(text):
                event.accept()
                return
            if text == '}' and self._outdent_brace_line():
                super().keyPressEvent(event)
                event.accept()
                return
        if text in PAIRS:
            if self._insert_pair(text):
                event.accept()
                return
        super().keyPressEvent(event)
        if text and (text.isalnum() or text == '_'):
            QTimer.singleShot(0, self._auto_complete)

    def _auto_complete(self):
        self.request_completion(force=False)

    def format_document(self):
        text = self.toPlainText()
        formatted = format_source(text)
        if formatted == text:
            return False
        cursor = self.textCursor()
        line = cursor.blockNumber()
        column = cursor.positionInBlock()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        cursor.insertText(formatted)
        cursor.endEditBlock()
        block = self.document().findBlockByNumber(min(line, max(0, self.document().blockCount() - 1)))
        restored = QTextCursor(block)
        restored.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor,
                             min(column, len(block.text())))
        self.setTextCursor(restored)
        return True
