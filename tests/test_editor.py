"""Formatting, auto-indent, bracket pairing and symbol completion tests."""
import os

import pytest

from mycc.gui.completion import collect_symbols
from mycc.gui.formatting import format_source


def test_formatter_indents_braces_and_normalises_spacing():
    source = 'int main(){\nif(1){\nreturn 0;\n}\n}\n'
    assert format_source(source) == (
        'int main() {\n'
        '    if (1) {\n'
        '        return 0;\n'
        '    }\n'
        '}\n'
    )
    # Compact teaching snippets are expanded, but initializer braces are not.
    assert format_source('int main(){return 0;}') == 'int main() {\n    return 0;\n}\n'
    assert format_source('if (x)\nreturn 0;\n') == 'if (x)\n    return 0;\n'
    assert 'int a[3] = {' in format_source('int a[3] = {1,2,3};')


def test_formatter_preserves_literals_and_comments():
    source = (
        'int main(void){\n'
        'printf("x } // not code", a); // }\n'
        '/* } */\n'
        'return 0;\n'
        '}\n'
    )
    formatted = format_source(source)
    assert '"x } // not code"' in formatted
    assert '// }' in formatted
    assert '/* } */' in formatted
    assert formatted.splitlines()[1].startswith('    printf')


def test_formatter_is_idempotent_and_ends_with_one_newline():
    source = 'int main() {\n    return 0;\n}\n\n\n'
    formatted = format_source(source)
    assert formatted == format_source(formatted)
    assert formatted.endswith('\n') and not formatted.endswith('\n\n')


def test_completion_offers_existing_variables_and_functions_but_not_comments():
    words = collect_symbols('int alpha; /* hidden */ int f(int beta){ return bet')
    assert {'alpha', 'f', 'beta', 'bet', 'printf', 'return'} <= set(words)
    assert 'hidden' not in words


def test_code_editor_auto_indent_pairing_and_format():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from mycc.gui.editor import CodeEditor

    app = QApplication.instance() or QApplication([])
    editor = CodeEditor()
    editor.show()
    editor.setPlainText('int main() {')
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key_Return)
    assert editor.toPlainText() == 'int main() {\n    '

    editor.setPlainText('if (x) ')
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key_BraceLeft)
    assert editor.toPlainText() == 'if (x) {}'
    assert editor.textCursor().position() == len('if (x) {')

    editor.setPlainText('int main(){\nif(1){\nreturn 0;\n}\n}\n')
    assert editor.format_document()
    assert editor.toPlainText() == (
        'int main() {\n    if (1) {\n        return 0;\n    }\n}\n'
    )
    assert not editor.format_document()
    editor.close()


def test_code_editor_completion_popup_uses_document_symbols():
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from mycc.gui.editor import CodeEditor

    app = QApplication.instance() or QApplication([])
    editor = CodeEditor()
    editor.show()
    editor.setPlainText('int alpha; int main(void){ int beta; al')
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.End)
    editor.setTextCursor(cursor)
    editor.setFocus()
    QTest.keyClick(editor, Qt.Key_P)
    QTest.qWait(100)
    assert editor.completer.popup().isVisible()
    assert {'alpha', 'beta', 'main', 'printf'} <= set(editor.completion_words())
    editor.close()
