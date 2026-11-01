"""Theme tokens and QSS for the PySide6 workbench.

The logic layer (`workbench.py`) stays Qt-free; this module is view-layer only.
Colours are plain strings so a theme can also be used by the syntax highlighter.
"""
from dataclasses import dataclass
from string import Template

from PySide6.QtGui import QPalette


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    window: str
    surface: str
    surface_alt: str
    raised: str
    border: str
    text: str
    muted: str
    accent: str
    accent_text: str
    editor_bg: str
    editor_fg: str
    selection: str
    current_line: str
    keyword: str
    number: str
    comment: str
    string: str
    error: str
    warning: str
    success: str


LIGHT = Theme(
    name='light', label='浅色',
    window='#f4f6f9', surface='#ffffff', surface_alt='#eef2f7', raised='#f8fafc',
    border='#d8dee8', text='#1f2937', muted='#667085',
    accent='#2563eb', accent_text='#ffffff',
    editor_bg='#ffffff', editor_fg='#1f2937', selection='#dbeafe', current_line='#f5f8ff',
    keyword='#7c3aed', number='#b45309', comment='#6b7280', string='#047857',
    error='#dc2626', warning='#b45309', success='#15803d',
)

DARK = Theme(
    name='dark', label='深色',
    window='#0f1115', surface='#161b22', surface_alt='#1b222c', raised='#212a35',
    border='#30363d', text='#e6edf3', muted='#8b949e',
    accent='#58a6ff', accent_text='#0d1117',
    editor_bg='#0d1117', editor_fg='#e6edf3', selection='#1f3a5f', current_line='#161b22',
    keyword='#ff7b72', number='#79c0ff', comment='#8b949e', string='#a5d6ff',
    error='#ff7b72', warning='#e3b341', success='#3fb950',
)

CONTRAST = Theme(
    name='contrast', label='高对比度',
    window='#000000', surface='#0a0a0a', surface_alt='#141414', raised='#1c1c1c',
    border='#f5d000', text='#ffffff', muted='#d0d0d0',
    accent='#f5d000', accent_text='#000000',
    editor_bg='#000000', editor_fg='#ffffff', selection='#333300', current_line='#141400',
    keyword='#f5d000', number='#7ee787', comment='#b8b8b8', string='#7ee787',
    error='#ff5555', warning='#f5d000', success='#7ee787',
)

THEMES = {t.name: t for t in (LIGHT, DARK, CONTRAST)}
CHOICES = (('system', '跟随系统'), ('light', '浅色'), ('dark', '深色'), ('contrast', '高对比度'))


def detect(app):
    """Pick light/dark from the platform palette (used by `system`)."""
    palette = app.palette() if app is not None else None
    if palette is not None:
        try:
            return DARK if palette.color(QPalette.Window).lightness() < 128 else LIGHT
        except (AttributeError, TypeError):
            pass
    return LIGHT


def resolve(name, app=None):
    if name == 'system':
        return detect(app)
    return THEMES.get(name, LIGHT)


def apply(app, name='system'):
    """Apply the QSS and return the concrete Theme that was selected."""
    chosen = resolve(name, app)
    if app is not None:
        app.setStyleSheet(qss(chosen))
        app.setProperty('mycc-theme', chosen.name)
    return chosen


def qss(t):
    """Stylesheet using $tokens; braces are literal, so string.Template is safe."""
    return Template(r"""
QMainWindow, QDialog { background: $window; color: $text; }
QWidget { color: $text; font-family: "Segoe UI", "Microsoft YaHei UI", "Noto Sans CJK SC", sans-serif; }
QMenuBar { background: $surface; border-bottom: 1px solid $border; padding: 2px 6px; }
QMenuBar::item { padding: 6px 10px; border-radius: 5px; background: transparent; }
QMenuBar::item:selected { background: $surface_alt; }
QMenu { background: $surface; border: 1px solid $border; border-radius: 8px; padding: 6px; }
QMenu::item { padding: 6px 26px 6px 12px; border-radius: 5px; }
QMenu::item:selected { background: $selection; color: $text; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }
QToolBar#MainToolBar { background: $surface; border: none; border-bottom: 1px solid $border; spacing: 4px; padding: 5px 10px; }
QToolBar#MainToolBar QToolButton { padding: 6px 10px; border: 1px solid transparent; border-radius: 6px; color: $text; }
QToolBar#MainToolBar QToolButton:hover { background: $surface_alt; border-color: $border; }
QToolBar#MainToolBar QToolButton:pressed { background: $selection; }
QToolBar#MainToolBar::separator { width: 1px; background: $border; margin: 4px 6px; }
QStatusBar { background: $surface; border-top: 1px solid $border; color: $muted; }
QStatusBar QLabel { color: $muted; padding: 1px 4px; }
QFrame#Header { background: $surface; border: 1px solid $border; border-radius: 10px; }
QLabel#Brand { font-size: 18px; font-weight: 700; color: $text; }
QLabel#Subtitle { color: $muted; font-size: 12px; }
QLabel#FileLabel { color: $muted; font-size: 12px; padding: 2px 4px; }
QLabel#Muted { color: $muted; }
QLabel#Accent { color: $accent; font-weight: 600; }
QGroupBox#Card { background: $surface; border: 1px solid $border; border-radius: 10px; margin-top: 14px; padding: 14px 10px 10px 10px; }
QGroupBox#Card::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: $muted; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox { background: $raised; border: 1px solid $border; border-radius: 6px; padding: 5px 8px; min-height: 20px; selection-background-color: $accent; selection-color: $accent_text; }
QLineEdit:focus, QComboBox:focus { border-color: $accent; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: $surface; border: 1px solid $border; selection-background-color: $selection; }
QPushButton { background: $raised; border: 1px solid $border; border-radius: 6px; padding: 6px 12px; }
QPushButton:hover { background: $surface_alt; border-color: $accent; }
QPushButton:pressed { background: $selection; }
QPushButton:disabled, QToolButton:disabled { color: $muted; }
QPushButton#Primary { background: $accent; color: $accent_text; border: none; font-weight: 600; }
QPushButton#Primary:hover { background: $accent; border: 1px solid $text; }
QPushButton#Primary:disabled { background: $surface_alt; color: $muted; border: 1px solid $border; }
QPushButton#Ghost { background: transparent; border: 1px solid $border; }
QLineEdit:disabled, QComboBox:disabled { color: $muted; background: $surface_alt; }
QCheckBox:disabled { color: $muted; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid $border; border-radius: 3px; background: $raised; }
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; }
QTabWidget::pane { border: 1px solid $border; border-radius: 8px; top: -1px; background: $surface; }
QTabBar::tab { background: transparent; color: $muted; padding: 7px 14px; border: none; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: $accent; border-bottom: 2px solid $accent; }
QTabBar::tab:hover { color: $text; background: $surface_alt; }
QPlainTextEdit, QTextEdit, QTextBrowser { background: $editor_bg; color: $editor_fg; border: 1px solid $border; border-radius: 8px; selection-background-color: $selection; selection-color: $editor_fg; }
QPlainTextEdit#Editor, QPlainTextEdit#LineNumbers { border: none; border-radius: 0; font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace; }
QPlainTextEdit#LineNumbers { background: $surface_alt; color: $muted; }
QPlainTextEdit#OutputView, QPlainTextEdit#CommandPreview { font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace; }
QTableWidget { background: $surface; alternate-background-color: $surface_alt; border: 1px solid $border; border-radius: 8px; gridline-color: $border; selection-background-color: $selection; }
QHeaderView::section { background: $surface_alt; color: $muted; border: none; border-bottom: 1px solid $border; padding: 5px 8px; }
QScrollArea { border: none; background: $window; }
QScrollArea#Sidebar, QScrollArea#Sidebar > QWidget > QWidget, QWidget#SidebarPanel { background: $window; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $muted; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 5px; min-width: 24px; }
QSplitter::handle { background: $border; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }
QToolTip { background: $surface; color: $text; border: 1px solid $accent; padding: 5px 8px; border-radius: 6px; }
QListWidget, QListView { background: $surface; border: 1px solid $border; border-radius: 8px; color: $text; selection-background-color: $selection; selection-color: $text; }
QListWidget::item, QListView::item { padding: 5px 6px; }
QListWidget::item:selected, QListView::item:selected { background: $selection; }
""").substitute(
        window=t.window, surface=t.surface, surface_alt=t.surface_alt, raised=t.raised,
        border=t.border, text=t.text, muted=t.muted, accent=t.accent, accent_text=t.accent_text,
        editor_bg=t.editor_bg, editor_fg=t.editor_fg, selection=t.selection,
    )
