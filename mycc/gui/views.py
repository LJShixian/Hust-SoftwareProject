"""Qt view layer for the mycc workbench.

The compiler logic stays in `workbench.py`; this module only builds widgets,
routes actions, and applies the selected theme.  PySide6 is imported dynamically
by `mycc.gui.app`, so `import mycc` still works without a Qt installation.
"""
from pathlib import Path
import os
import threading

import PySide6
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Qt, QEvent, QSize
from PySide6.QtGui import (QAction, QFont, QKeySequence, QTextCursor, QColor,
                           QSyntaxHighlighter, QTextCharFormat)
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QSplitter, QPlainTextEdit, QTabWidget, QComboBox, QCheckBox, QLabel,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QAbstractItemView, QTextEdit,
    QApplication, QScrollArea, QMenu, QToolBar, QToolButton, QGroupBox, QLineEdit,
    QPushButton, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QStyle, QFrame,
    QTextBrowser, QHeaderView)
from . import workbench as model
from . import theme as theming
from .editor import CodeEditor
from .. import __version__


ACTION_HINTS = {
    '新建': '清空编辑器，新建一个未命名的源文件（会先询问是否保存当前修改）',
    '打开': '打开一个 .c 源文件；上限 128 KiB，按 UTF-8 解码',
    '保存': '把编辑器内容写回源文件；未命名时等同于另存为',
    '另存为': '选择新路径保存当前源码',
    '导出当前页…': '把下方当前选中的输出页存成文件：汇编存 .s，Lowering 报告存 .md，其余存 .txt',
    '编译': '按当前目标、profile、ISA 和输出选项编译（F5）。编译失败时保留上一次成功的汇编',
    '取消编译': '中止正在进行的编译；只在编译过程中可用',
    '放大': '放大编辑器字号（只影响显示，不影响产物）',
    '缩小': '缩小编辑器字号（只影响显示，不影响产物）',
    '关于': '版本号、当前主题与第三方组件许可说明',
    '外部工具与适配说明': '如何用外部工具链把生成的汇编变成可执行文件或板卡镜像',
    '命令预览': '显示与当前 GUI 选项完全等价的命令行，并可复制到终端执行',
    '环境自检': '检查 Python、PySide6、适配器和外部工具链是否可用',
    'ISA 详情': '查看当前 profile 的指令清单、白名单和指纹',
    'CLI 开关': '查看每个命令行开关在 GUI 中的对应位置',
    '显示侧栏': '显示或隐藏左侧设置侧栏',
    '显示底部面板': '显示或隐藏诊断与输出面板',
    '主题': '切换浅色、深色或高对比度主题；可跟随系统',
    '格式化文档': '按 4 空格缩进、括号层级和统一空格整理当前源文件（Ctrl+Shift+F）',
    '撤销': '撤销上一个编辑操作（Ctrl+Z）',
    '重做': '重做被撤销的编辑操作（Ctrl+Y）',
    '剪切': '剪切选中的源码（Ctrl+X）',
    '复制': '复制选中的源码（Ctrl+C）',
    '粘贴': '粘贴剪贴板内容（Ctrl+V）',
    '全选': '选中编辑器中的全部源码（Ctrl+A）',
}

TAB_HINTS = [
    '汇编：最终生成的 GNU RISC-V 汇编。Ctrl+Shift+E 可存成 .s',
    'Token：词法分析结果（行:列、记号类别、原文）。语法报错时先看这里',
    'AST：语法树，每个节点带 @行:列。用来核对运算符优先级、括号配对、if/else 归属',
    'IR：代码生成期间记录的操作序列（CONST32、BIN_MUL、CALL 等）',
    'Lowering 报告：每个“缺指令”决策的明细——源码位置、选中实现、被拒方案、Δ 指令',
]

OUTPUT_TITLES = ['汇编', 'Token', 'AST', 'IR', 'Lowering 报告']
TAB_DUMP_KEYS = {'Token': 'tokens', 'AST': 'ast', 'IR': 'ir', 'Lowering 报告': 'lowering_report'}

GROUP_HINTS = {
    'mul': '硬件乘法（M 扩展 mul）。取消勾选则改调软件乘法 __mulsi3，每处多 2 条指令',
    'divrem': '硬件除法与取余（div / rem）。取消勾选则调 __divsi3 / __modsi3',
    'xor': '硬件按位异或。取消勾选则用 (a|b)-(a&b) 三条指令合成',
    'cmpbr': '额外的比较分支（bge / bgeu / bltu / sltiu）。取消勾选则用 blt 组合回退',
    'byteload': '字节与半字加载（lb / lbu / lh / lhu）。语言本身仍不支持 char，这项只是预留能力',
    'auipc': 'PC 相对高位加载（auipc）。取消勾选则改用 jal 取 PC 的方式算地址',
    'lui': '立即数高位加载（--no-lui 等价于取消此项）。取消后大常量和全局地址走“字节合成”',
    'vshift': '寄存器移位（sll / srl / sra；--no-vshift 等价于取消此项）。取消后移位改调软件辅助函数',
}

TARGET_HINTS = {
    'generic': '通用 GNU 汇编，地址/启动由外部工具链决定；可选 RARS 单文件输出',
    'cpu21': 'CPU21 板卡的启动、地址与外设约定；不接受 RARS/Logisim 输出',
    'logisim': 'Logisim 课堂 CPU（PF-08）：1024 字 ROM、1024 字节 RAM、无链接器；默认栈顶 1024',
}

CLI_SWITCHES = [
    ('source.c', '输入 C 源文件（位置参数）', '文件 → 打开 / 编辑器'),
    ('-o PATH', '输出汇编或镜像路径', '构建与输出 → 输出路径'),
    ('--target T', 'generic / cpu21 / logisim', '构建与输出 → 目标'),
    ('--rars', '输出 RARS 可加载的单文件汇编', '构建与输出 → RARS 单文件'),
    ('--logisim', '输出 Logisim ROM/RAM 镜像（必须配 --target logisim）', '构建与输出 → Logisim 镜像'),
    ('--stack-top N', '栈顶地址（支持 0x 前缀）', '构建与输出 → 栈顶'),
    ('--profile P', 'PF-01…PF-08 / cpu21', '指令集 → Profile'),
    ('--isa-file JSON', '从 JSON 读入自定义 ISA', '指令集 → ISA 文件'),
    ('--enable NAME', '显式启用一个组或单条指令', '指令集 → 组复选框 / 自定义指令'),
    ('--disable NAME', '显式禁用一个组或单条指令', '指令集 → 组复选框 / 自定义指令'),
    ('--no-lui', '等价于 --disable lui', '指令集 → 取消勾选 lui'),
    ('--no-vshift', '等价于 --disable vshift', '指令集 → 取消勾选 vshift'),
    ('--dump-tokens', '打印 Token 表', '输出与诊断 → 显示 Token'),
    ('--dump-ast', '打印 AST', '输出与诊断 → 显示 AST'),
    ('--dump-ir', '打印 IR 操作序列', '输出与诊断 → 显示 IR'),
    ('--dump-isa', '打印当前 ISA 清单', 'ISA 详情按钮'),
    ('--dump-isa-whitelist', '打印后端白名单', 'ISA 详情按钮'),
    ('--dump-lowering-report', '打印 lowering 决策报告', '输出与诊断 → 显示 Lowering'),
    ('--stats', '打印各阶段耗时', '输出与诊断 → 显示耗时'),
    ('--doctor', '环境自检', '构建 → 环境自检'),
    ('--version', '版本信息', '帮助 → 关于 / 状态栏版本'),
    ('--gui', '启动 PySide6 工作台', '当前窗口本身'),
]


class Signals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class Worker(QRunnable):
    def __init__(self, request):
        super().__init__()
        self.request = request
        self.signals = Signals()
        self.cancel = threading.Event()

    def run(self):
        try:
            req = self.request
            req.options.cancelled = self.cancel.is_set
            res = model.core.compile(req.src, req.profile, options=req.options)
            self.signals.finished.emit(res)
        except Exception as exc:
            self.signals.failed.emit(f'{type(exc).__name__}: {exc}')


class Highlighter(QSyntaxHighlighter):
    def __init__(self, document, palette):
        super().__init__(document)
        self.palette = palette

    def set_palette(self, palette):
        self.palette = palette
        self.rehighlight()

    def highlightBlock(self, text):
        import re
        p = self.palette
        for pattern, color in [
            (r'\b(int|void|if|else|while|for|return|break|continue|sizeof)\b', p.keyword),
            (r'\b(0[xX][0-9a-fA-F]+|[0-9]+)\b', p.number),
            (r'//.*$', p.comment),
        ]:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            for match in re.finditer(pattern, text):
                self.setFormat(match.start(), len(match.group()), fmt)
        comment = QTextCharFormat()
        comment.setForeground(QColor(p.comment))
        start = 0 if self.previousBlockState() == 1 else text.find('/*')
        self.setCurrentBlockState(0)
        while start >= 0:
            end = text.find('*/', start + 2)
            if end < 0:
                self.setFormat(start, len(text) - start, comment)
                self.setCurrentBlockState(1)
                break
            self.setFormat(start, end + 2 - start, comment)
            start = text.find('/*', end + 2)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        app = QApplication.instance()
        if app is not None:
            app.setStyle('Fusion')
            QApplication.setFont(QFont('Microsoft YaHei', 10))

        settings, message = model.load_settings()
        self.state = model.state_from_settings(settings)
        self._sanitize_state()
        self._loading = True
        self._settings_message = message
        self.hint_texts = {}
        self.hovering = False
        self.status_text = ''
        self.diag_rows = []
        self.outputs = {}
        self.actions = {}
        self.theme_actions = {}
        self.palette = theming.resolve(self.state.theme, app)
        self.pool = QThreadPool.globalInstance()
        self.worker = None

        self.resize(1320, 870)
        self.setMinimumSize(980, 640)
        self._build_central()
        self._build_actions()
        self._apply_initial_state(self._settings_message)
        self.apply_theme(self.state.theme, persist=False)
        self._loading = False
        self.set_status(self._settings_message or
                        '就绪 · F5 编译 · Ctrl+Shift+P 命令预览 · Ctrl+Shift+I ISA 详情')
        self.update_position()
        self.update_header()
        if app is not None:
            app.installEventFilter(self)

    # ------------------------------------------------------------------ state
    def _sanitize_state(self):
        """Keep persisted target/profile/output combinations self-consistent."""
        if self.state.logisim:
            self.state.target = 'logisim'
        if self.state.target == 'logisim':
            self.state.baseline = 'PF-08'
            self.state.rars = self.state.logisim = True
        elif self.state.target == 'cpu21':
            self.state.baseline = 'cpu21'
            self.state.rars = self.state.logisim = False
        else:
            if self.state.baseline in ('cpu21', 'PF-08'):
                self.state.baseline = 'PF-01'
            self.state.logisim = False
        if not isinstance(self.state.dumps, dict):
            self.state.dumps = dict(model.DEFAULT_DUMPS)
        for key in model.DUMP_KEYS:
            self.state.dumps.setdefault(key, model.DEFAULT_DUMPS[key])

    # --------------------------------------------------------------- widgets
    def _card(self, title):
        box = QGroupBox(title)
        box.setObjectName('Card')
        layout = QVBoxLayout(box)
        layout.setContentsMargins(12, 18, 12, 12)
        layout.setSpacing(8)
        return box, layout

    def _form_card(self, title):
        box, outer = self._card(title)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        outer.addLayout(form)
        return box, form, outer

    def _row(self, *widgets):
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        for widget in widgets:
            h.addWidget(widget)
        return row

    def _build_central(self):
        self.editor = CodeEditor()
        self.editor.setObjectName('Editor')
        code_font = QFont('Cascadia Mono', 11)
        code_font.setStyleHint(QFont.Monospace)
        self.editor.setFont(code_font)
        self.editor.document().setDefaultFont(code_font)
        self.editor.setPlainText(self.state.text)
        self.editor.document().setModified(False)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(' ') * 4)
        self.editor.setPlaceholderText('在此输入 C 源文件，或按 Ctrl+O 打开…')
        self.line_numbers = QPlainTextEdit()
        self.line_numbers.setObjectName('LineNumbers')
        self.line_numbers.setFont(code_font)
        self.line_numbers.setReadOnly(True)
        self.line_numbers.setFocusPolicy(Qt.NoFocus)
        self.line_numbers.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.line_numbers.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.line_numbers.setFixedWidth(54)
        self.highlighter = Highlighter(self.editor.document(), self.palette)

        header = QFrame()
        header.setObjectName('Header')
        h = QHBoxLayout(header)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)
        self.file_label = QLabel('未命名')
        self.file_label.setObjectName('FileLabel')
        self.header_meta = QLabel('')
        self.header_meta.setObjectName('Muted')
        self.header_meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(self.file_label)
        h.addStretch(1)
        h.addWidget(self.header_meta)

        source = QWidget()
        sh = QHBoxLayout(source)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(0)
        sh.addWidget(self.line_numbers)
        sh.addWidget(self.editor, 1)

        editor_box = QWidget()
        ev = QVBoxLayout(editor_box)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(6)
        ev.addWidget(header)
        ev.addWidget(source, 1)

        self.diagnostics = QTableWidget(0, 4)
        self.diagnostics.setObjectName('Diagnostics')
        self.diagnostics.setHorizontalHeaderLabels(['级别', '位置', '诊断', '错误码'])
        self.diagnostics.verticalHeader().setVisible(False)
        self.diagnostics.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.diagnostics.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.diagnostics.setAlternatingRowColors(True)
        self.diagnostics.setShowGrid(False)
        self.diagnostics.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.diagnostics.setColumnWidth(0, 70)
        self.diagnostics.setColumnWidth(1, 90)
        self.diagnostics.setColumnWidth(3, 130)
        self.diagnostics.cellDoubleClicked.connect(self.jump)

        self.tabs = QTabWidget()
        self.tabs.setObjectName('OutputTabs')
        self.tabs.setDocumentMode(True)
        for title, hint in zip(OUTPUT_TITLES, TAB_HINTS):
            view = QPlainTextEdit()
            view.setObjectName('OutputView')
            view.setReadOnly(True)
            view.setPlaceholderText(hint)
            view.setLineWrapMode(QPlainTextEdit.NoWrap)
            self.outputs[title] = view
            self.tabs.addTab(view, title)
        self.tabs.tabBar().setMouseTracking(True)
        self.tabs.tabBar().installEventFilter(self)
        self.tabs.currentChanged.connect(self._tab_changed)

        right = QSplitter(Qt.Vertical)
        right.setObjectName('WorkArea')
        right.addWidget(editor_box)
        right.addWidget(self.diagnostics)
        right.addWidget(self.tabs)
        right.setStretchFactor(0, 5)
        right.setStretchFactor(1, 1)
        right.setStretchFactor(2, 3)
        right.setSizes([520, 130, 260])
        right.setChildrenCollapsible(True)

        self.sidebar_scroll = self._build_sidebar()
        split = QSplitter(Qt.Horizontal)
        split.setObjectName('MainSplit')
        split.addWidget(self.sidebar_scroll)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([370, 950])
        split.setChildrenCollapsible(False)
        self.main_split = split
        self.work_area = right
        self.editor_box = editor_box
        self.setCentralWidget(split)

        self.editor.textChanged.connect(self.changed)
        self.editor.cursorPositionChanged.connect(self.highlight)
        self.editor.cursorPositionChanged.connect(self.update_position)
        self.editor.document().modificationChanged.connect(lambda _: self.update_header())
        self.editor.cursorPositionChanged.connect(self.update_numbers)
        self.editor.textChanged.connect(self.update_numbers)
        self.update_numbers()

        status = self.statusBar()
        self.status_label = QLabel('就绪')
        self.status_label.setObjectName('Muted')
        self.position_label = QLabel('Ln 1, Col 1')
        self.position_label.setObjectName('Muted')
        self.theme_label = QLabel('')
        self.theme_label.setObjectName('Muted')
        self.version_label = QLabel(f'v{__version__}')
        self.version_label.setObjectName('Muted')
        status.addWidget(self.status_label, 1)
        status.addPermanentWidget(self.position_label)
        status.addPermanentWidget(self.theme_label)
        status.addPermanentWidget(self.version_label)

    def _build_sidebar(self):
        scroll = QScrollArea()
        scroll.setObjectName('Sidebar')
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(340)
        scroll.setMaximumWidth(470)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel = QWidget()
        panel.setObjectName('SidebarPanel')
        v = QVBoxLayout(panel)
        v.setContentsMargins(14, 12, 14, 18)
        v.setSpacing(10)

        brand = QFrame()
        brand.setObjectName('Header')
        bh = QHBoxLayout(brand)
        bh.setContentsMargins(12, 10, 12, 10)
        title = QLabel('mycc')
        title.setObjectName('Brand')
        subtitle = QLabel('C 子集 → RISC-V\n可配置 ISA 工作台')
        subtitle.setObjectName('Subtitle')
        bh.addWidget(title)
        bh.addStretch(1)
        bh.addWidget(subtitle)
        v.addWidget(brand)

        build, build_form, _ = self._form_card('构建与输出')
        self.target_combo = QComboBox()
        for value, label in (('generic', '通用 GNU 汇编'), ('cpu21', 'CPU21 板卡'),
                             ('logisim', 'Logisim 课堂 CPU')):
            self.target_combo.addItem(label, value)
        build_form.addRow('目标', self.target_combo)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText('文件或文件夹；如 build/demo.asm 或 build/out')
        self.output_button = QPushButton('文件…')
        self.output_button.setObjectName('Ghost')
        self.output_dir_button = QPushButton('文件夹…')
        self.output_dir_button.setObjectName('Ghost')
        build_form.addRow('输出路径', self.output_edit)
        build_form.addRow('', self._row(self.output_button, self.output_dir_button))
        self.write_output = QCheckBox('编译成功后写入输出路径')
        build_form.addRow('', self.write_output)
        self.rars_check = QCheckBox('RARS 单文件（--rars）')
        self.logisim_check = QCheckBox('Logisim 镜像（--logisim）')
        build_form.addRow('输出格式', self.rars_check)
        build_form.addRow('', self.logisim_check)
        self.stack_edit = QLineEdit()
        self.stack_edit.setPlaceholderText('留空：RARS 使用约定值，Logisim 默认 1024')
        build_form.addRow('栈顶', self.stack_edit)
        self.attach_hint(self.target_combo, TARGET_HINTS['generic'])
        self.attach_hint(self.rars_check, '把转换后的 RARS 单文件汇编写到输出路径；仅通用目标可用')
        self.attach_hint(self.logisim_check, '自动切到 Logisim 目标并写出 .asm/.rom.hex/.ram.hex')
        self.attach_hint(self.stack_edit, 'CLI 的 --stack-top；只影响 RARS/Logisim 产物')
        self.attach_hint(self.output_edit, 'CLI 的 -o；可填文件或文件夹，勾选“编译成功后写入”才会落盘')
        self.attach_hint(self.output_button, '选择一个输出文件；留空的文件名会使用源文件名')
        self.attach_hint(self.output_dir_button, '选择一个输出文件夹；按源文件名写入 .s/.asm 与镜像')
        v.addWidget(build)

        isa, isa_form, isa_outer = self._form_card('指令集')
        self.profile = QComboBox()
        for index, name in enumerate(model.core.PRESETS, 1):
            value = 'cpu21' if name == 'cpu21' else f'PF-{index:02}'
            label = 'cpu21 · 硬件参考 ISA' if name == 'cpu21' else f'PF-{index:02} · {name}'
            self.profile.addItem(label, value)
        isa_form.addRow('Profile', self.profile)
        self.checkboxes = {}
        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 2)
        grid.setHorizontalSpacing(8)
        for i, name in enumerate(model.core.GROUPS):
            if name == 'm' or name.startswith('EX-'):
                continue
            cb = QCheckBox(name)
            cb.setToolTip(GROUP_HINTS.get(name, name))
            self.checkboxes[name] = cb
            grid.addWidget(cb, i // 2, i % 2)
        isa_outer.addLayout(grid)
        compat = QWidget()
        ch = QHBoxLayout(compat)
        ch.setContentsMargins(0, 0, 0, 0)
        self.no_lui_check = QCheckBox('--no-lui')
        self.no_vshift_check = QCheckBox('--no-vshift')
        ch.addWidget(self.no_lui_check)
        ch.addWidget(self.no_vshift_check)
        ch.addStretch(1)
        isa_form.addRow('兼容开关', compat)
        self.isa_file_edit = QLineEdit()
        self.isa_file_edit.setPlaceholderText('可选：自定义 ISA JSON')
        self.isa_file_button = QPushButton('浏览…')
        self.isa_file_button.setObjectName('Ghost')
        isa_form.addRow('ISA 文件', self._row(self.isa_file_edit, self.isa_file_button))
        self.custom_isa_button = QPushButton('自定义单条指令…')
        self.custom_isa_button.setObjectName('Ghost')
        isa_form.addRow('', self.custom_isa_button)
        self.isa_summary = QLabel('')
        self.isa_summary.setObjectName('Muted')
        self.isa_summary.setWordWrap(True)
        isa_form.addRow('', self.isa_summary)
        self.isa_detail_button = QPushButton('查看 ISA 详情')
        self.isa_detail_button.setObjectName('Ghost')
        isa_form.addRow('', self.isa_detail_button)
        self.attach_hint(self.profile, '命令行的 --profile；会清空手动的 enable/disable 差异')
        self.attach_hint(self.isa_file_edit, '命令行的 --isa-file；文件存在时覆盖 profile 的指令集合')
        self.attach_hint(self.no_lui_check, '等价于取消勾选 lui（CLI: --no-lui）')
        self.attach_hint(self.no_vshift_check, '等价于取消勾选 vshift（CLI: --no-vshift）')
        v.addWidget(isa)

        view, view_form, view_outer = self._form_card('输出与外观')
        self.dump_checks = {}
        dump_grid = QGridLayout()
        dump_grid.setContentsMargins(0, 0, 0, 0)
        labels = [('tokens', '显示 Token'), ('ast', '显示 AST'), ('ir', '显示 IR'),
                  ('lowering_report', '显示 Lowering'), ('isa', '命令含 --dump-isa'),
                  ('isa_whitelist', '命令含 --dump-isa-whitelist')]
        for i, (key, label) in enumerate(labels):
            cb = QCheckBox(label)
            self.dump_checks[key] = cb
            dump_grid.addWidget(cb, i, 0)
        view_outer.addLayout(dump_grid)
        self.stats_check = QCheckBox('显示各阶段耗时（--stats）')
        view_form.addRow('', self.stats_check)
        self.theme_combo = QComboBox()
        for value, label in theming.CHOICES:
            self.theme_combo.addItem(label, value)
        view_form.addRow('主题', self.theme_combo)
        self.attach_hint(self.stats_check, '在状态栏显示词法/语法/语义/生成分别耗时')
        self.attach_hint(self.theme_combo, '浅色、深色、高对比度或跟随系统；立即生效并保存')
        v.addWidget(view)

        quick, quick_form, _ = self._form_card('快捷操作')
        self.command_button = QPushButton('命令预览与复制')
        self.command_button.setObjectName('Primary')
        self.doctor_button = QPushButton('环境自检')
        self.doctor_button.setObjectName('Ghost')
        self.cli_help_button = QPushButton('CLI 开关对照')
        self.cli_help_button.setObjectName('Ghost')
        quick_form.addRow(self.command_button)
        quick_form.addRow(self.doctor_button)
        quick_form.addRow(self.cli_help_button)
        self.attach_hint(self.command_button, '显示与当前 GUI 等价的 python -m mycc 命令')
        v.addWidget(quick)
        v.addStretch(1)
        scroll.setWidget(panel)

        self.target_combo.currentIndexChanged.connect(self.target_changed)
        self.profile.currentIndexChanged.connect(self.profile_changed)
        self.output_edit.textChanged.connect(self.output_changed)
        self.output_button.clicked.connect(self.browse_output)
        self.output_dir_button.clicked.connect(self.browse_output_dir)
        self.write_output.toggled.connect(self.write_output_changed)
        self.rars_check.toggled.connect(self.rars_changed)
        self.logisim_check.toggled.connect(self.logisim_changed)
        self.stack_edit.textChanged.connect(self.stack_changed)
        self.isa_file_edit.textChanged.connect(self.isa_file_changed)
        self.isa_file_button.clicked.connect(self.browse_isa)
        self.custom_isa_button.clicked.connect(self.custom_instructions)
        self.isa_detail_button.clicked.connect(self.show_isa_details)
        self.no_lui_check.toggled.connect(self.no_lui_changed)
        self.no_vshift_check.toggled.connect(self.no_vshift_changed)
        for key, cb in self.dump_checks.items():
            cb.toggled.connect(self.dump_changed)
        self.stats_check.toggled.connect(self.stats_changed)
        self.theme_combo.currentIndexChanged.connect(self.theme_changed)
        self.command_button.clicked.connect(self.show_command_preview)
        self.doctor_button.clicked.connect(self.show_doctor)
        self.cli_help_button.clicked.connect(self.show_cli_help)
        for cb in self.checkboxes.values():
            cb.toggled.connect(self.capability_changed)
        return scroll

    # --------------------------------------------------------------- actions
    def _build_actions(self):
        self.menus = {}
        for name in ('文件', '编辑', '构建', '格式', '视图', '帮助'):
            menu = QMenu(name, self)
            self.menuBar().addMenu(menu)
            self.menus[name] = menu

        def action(key, label, slot, shortcuts=None, menu='文件', hint='', icon=None, checkable=False):
            item = QAction(label, self)
            item.setCheckable(checkable)
            item.triggered.connect(slot)
            if shortcuts:
                seqs = [shortcuts] if isinstance(shortcuts, str) else list(shortcuts)
                item.setShortcuts([QKeySequence(seq) for seq in seqs])
            if hint:
                item.setStatusTip(hint)
                item.setToolTip(hint)
                item.hovered.connect(lambda text=hint: self.describe(text))
            if icon is not None:
                item.setIcon(icon)
            self.menus[menu].addAction(item)
            self.actions[key] = item
            return item

        std = self.style()
        icon_new = std.standardIcon(QStyle.SP_FileIcon)
        icon_open = std.standardIcon(QStyle.SP_DialogOpenButton)
        icon_save = std.standardIcon(QStyle.SP_DialogSaveButton)
        icon_run = std.standardIcon(QStyle.SP_MediaPlay)
        icon_stop = std.standardIcon(QStyle.SP_BrowserStop)
        icon_theme = std.standardIcon(QStyle.SP_DesktopIcon)

        action('new', '新建', self.new_file, 'Ctrl+N', hint=ACTION_HINTS['新建'], icon=icon_new)
        action('open', '打开…', self.open_file, 'Ctrl+O', hint=ACTION_HINTS['打开'], icon=icon_open)
        action('save', '保存', self.save_file, 'Ctrl+S', hint=ACTION_HINTS['保存'], icon=icon_save)
        action('save_as', '另存为…', self.save_as, 'Ctrl+Shift+S', hint=ACTION_HINTS['另存为'])
        action('export', '导出当前页…', self.export_current, 'Ctrl+Shift+E', hint=ACTION_HINTS['导出当前页…'])
        self.menus['文件'].addSeparator()
        action('quit', '退出', self.close, 'Ctrl+Q', hint='保存设置并退出工作台')

        action('undo', '撤销', self.editor.undo, menu='编辑', hint=ACTION_HINTS['撤销'])
        action('redo', '重做', self.editor.redo, menu='编辑', hint=ACTION_HINTS['重做'])
        self.menus['编辑'].addSeparator()
        action('cut', '剪切', self.editor.cut, menu='编辑', hint=ACTION_HINTS['剪切'])
        action('copy', '复制', self.editor.copy, menu='编辑', hint=ACTION_HINTS['复制'])
        action('paste', '粘贴', self.editor.paste, menu='编辑', hint=ACTION_HINTS['粘贴'])
        self.menus['编辑'].addSeparator()
        action('select_all', '全选', self.editor.selectAll, menu='编辑', hint=ACTION_HINTS['全选'])

        self.format_action = action(
            'format', '格式化文档', self.format_document, 'Ctrl+Shift+F', '格式',
            ACTION_HINTS['格式化文档'], icon=std.standardIcon(QStyle.SP_FileDialogDetailedView))
        self.menus['格式'].addSeparator()
        action('indent', '选中行增加缩进', lambda: self.editor.indent_selection(False),
               'Ctrl+]', '格式', '增加一行或选中行的缩进')
        action('outdent', '选中行减少缩进', lambda: self.editor.indent_selection(True),
               'Ctrl+[', '格式', '减少一行或选中行的缩进')

        self.compile_action = action('compile', '编译', self.start_compile, 'F5', '构建',
                                     ACTION_HINTS['编译'], icon_run)
        self.cancel_action = action('cancel', '取消编译', self.cancel_compile, menu='构建',
                                    hint=ACTION_HINTS['取消编译'], icon=icon_stop)
        self.cancel_action.setEnabled(False)
        self.menus['构建'].addSeparator()
        action('isa', 'ISA 详情…', self.show_isa_details, 'Ctrl+Shift+I', '构建',
               ACTION_HINTS['ISA 详情'])
        action('command', '命令预览…', self.show_command_preview, 'Ctrl+Shift+P', '构建',
               ACTION_HINTS['命令预览'])
        action('doctor', '环境自检…', self.show_doctor, 'Ctrl+Shift+D', '构建',
               ACTION_HINTS['环境自检'])

        action('zoom_in', '放大', lambda: self.zoom(1), ('Ctrl++', 'Ctrl+=', 'Ctrl+Shift+='),
               '视图', ACTION_HINTS['放大'])
        action('zoom_out', '缩小', lambda: self.zoom(-1), ('Ctrl+-', 'Ctrl+_', 'Ctrl+Shift+-'),
               '视图', ACTION_HINTS['缩小'])
        self.sidebar_action = action('sidebar', '显示侧栏', self.toggle_sidebar, menu='视图',
                                     hint=ACTION_HINTS['显示侧栏'], checkable=True)
        self.sidebar_action.setChecked(True)
        self.bottom_action = action('bottom', '显示底部面板', self.toggle_bottom, menu='视图',
                                    hint=ACTION_HINTS['显示底部面板'], checkable=True)
        self.bottom_action.setChecked(True)
        self.menus['视图'].addSeparator()
        self.theme_menu = QMenu('主题', self)
        for name, label in theming.CHOICES:
            item = QAction(label, self)
            item.setCheckable(True)
            item.triggered.connect(lambda checked, n=name: self.apply_theme(n))
            self.theme_menu.addAction(item)
            self.theme_actions[name] = item
        self.menus['视图'].addMenu(self.theme_menu)

        action('cli_help', 'CLI 开关对照…', self.show_cli_help, 'Ctrl+Shift+K', '帮助',
               ACTION_HINTS['CLI 开关'])
        action('external', '外部工具与适配说明', self.external_tools_help, menu='帮助',
               hint=ACTION_HINTS['外部工具与适配说明'])
        action('about', '关于', self.show_about, menu='帮助', hint=ACTION_HINTS['关于'])

        toolbar = QToolBar('主工具栏')
        toolbar.setObjectName('MainToolBar')
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        for key in ('new', 'open', 'save'):
            toolbar.addAction(self.actions[key])
        toolbar.addSeparator()
        self.compile_button = QPushButton('▶  编译')
        self.compile_button.setObjectName('Primary')
        self.compile_button.setToolTip('按当前设置编译（F5）')
        self.compile_button.clicked.connect(self.start_compile)
        self.cancel_button = QPushButton('停止')
        self.cancel_button.setObjectName('Ghost')
        self.cancel_button.setToolTip('取消正在运行的编译')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_compile)
        toolbar.addWidget(self.compile_button)
        toolbar.addWidget(self.cancel_button)
        toolbar.addAction(self.format_action)
        toolbar.addSeparator()
        toolbar.addAction(self.actions['command'])
        toolbar.addAction(self.actions['doctor'])
        toolbar.addSeparator()
        theme_button = QToolButton()
        theme_button.setObjectName('ThemeButton')
        theme_button.setText('主题')
        theme_button.setIcon(icon_theme)
        theme_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        theme_button.setPopupMode(QToolButton.InstantPopup)
        theme_button.setMenu(self.theme_menu)
        toolbar.addWidget(theme_button)
        self.toolbar = toolbar
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        for menu in self.menus.values():
            menu.aboutToHide.connect(lambda: self.describe(''))

    # ------------------------------------------------------------- load state
    def _apply_initial_state(self, message):
        self._loading = True
        idx = self.profile.findData(self.state.baseline)
        self.profile.setCurrentIndex(max(0, idx))
        self.target_combo.setCurrentIndex(max(0, self.target_combo.findData(self.state.target)))
        self.output_edit.setText(self.state.output)
        self.write_output.setChecked(self.state.write_output)
        self.rars_check.setChecked(self.state.rars)
        self.logisim_check.setChecked(self.state.logisim)
        self.stack_edit.setText(self.state.stack_top)
        self.isa_file_edit.setText(self.state.isa_file)
        for key, cb in self.dump_checks.items():
            cb.setChecked(bool(self.state.dumps.get(key, model.DEFAULT_DUMPS[key])))
        self.stats_check.setChecked(self.state.stats)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self.state.theme)))
        self._loading = False
        self.sync_capabilities()
        self._sync_option_states()
        self.apply_dump_visibility()
        self.update_header()
        self.set_status(message or '就绪 · F5 编译 · Ctrl+Shift+P 命令预览')

    def _sync_option_states(self):
        target = self.state.target
        is_generic = target == 'generic'
        self.profile.setEnabled(is_generic)
        self.rars_check.blockSignals(True)
        self.rars_check.setChecked(self.state.rars)
        self.rars_check.setEnabled(is_generic)
        self.rars_check.blockSignals(False)
        self.logisim_check.blockSignals(True)
        self.logisim_check.setChecked(self.state.logisim or target == 'logisim')
        self.logisim_check.setEnabled(is_generic)
        self.logisim_check.blockSignals(False)
        self.stack_edit.setEnabled(target != 'cpu21')
        self.output_edit.setEnabled(True)
        self.write_output.setEnabled(True)
        self.attach_hint(self.target_combo, TARGET_HINTS.get(target, TARGET_HINTS['generic']))

    def _select_profile(self, name):
        idx = self.profile.findData(name)
        if idx < 0:
            return
        self.profile.blockSignals(True)
        self.profile.setCurrentIndex(idx)
        self.profile.blockSignals(False)
        self.state.baseline = name
        self.state.enable = []
        self.state.disable = []

    # -------------------------------------------------------------- reactions
    def changed(self):
        if self._loading:
            return
        self.state.text = self.editor.toPlainText()
        self.state.stale = True
        if self.state.last_asm:
            self.tabs.setTabText(0, '汇编 · 内容已过期')
        self.update_header()

    def format_document(self):
        if not self.editor.toPlainText().strip():
            self.set_status('当前文件为空，无需格式化')
            return
        changed = self.editor.format_document()
        self.state.text = self.editor.toPlainText()
        self.state.stale = True
        if changed:
            if self.state.last_asm:
                self.tabs.setTabText(0, '汇编 · 内容已过期')
            self.set_status('已格式化当前文件（4 空格缩进，Ctrl+Z 可撤销）')
        else:
            self.set_status('当前文件已经符合格式化规则')
        self.update_header()

    def profile_changed(self):
        if self._loading:
            return
        self.state.baseline = self.profile.currentData()
        self.state.enable = []
        self.state.disable = []
        self.sync_capabilities()
        self.changed()
        self.set_status('profile 已修改，下次编译生效')

    def sync_capabilities(self):
        try:
            profile = model.profile_for_state(self.state)
        except (model.core.ProfileError, OSError, ValueError) as exc:
            self.isa_summary.setText(f'配置错误：{exc}')
            return
        for name, cb in self.checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(model.core.GROUPS[name] <= profile.instructions)
            cb.blockSignals(False)
        self.no_lui_check.blockSignals(True)
        self.no_lui_check.setChecked(not (model.core.GROUPS['lui'] <= profile.instructions))
        self.no_lui_check.blockSignals(False)
        self.no_vshift_check.blockSignals(True)
        self.no_vshift_check.setChecked(not (model.core.GROUPS['vshift'] <= profile.instructions))
        self.no_vshift_check.blockSignals(False)
        self.isa_summary.setText(f'{len(profile.instructions)} 条指令 · MV-ISA 满足\n'
                                 f'{self.state.target} · 下次编译生效')
        self.update_header()

    def capability_changed(self):
        if self._loading:
            return
        enabled = [name for name, cb in self.checkboxes.items() if cb.isChecked()]
        disabled = [name for name, cb in self.checkboxes.items() if not cb.isChecked()]
        self.state.enable, self.state.disable = model.normalize_capabilities(
            self.state.baseline, enabled, disabled)
        self.sync_capabilities()
        self.changed()
        self.set_status('profile 已修改，下次编译生效')

    def no_lui_changed(self, checked):
        if self._loading:
            return
        self.checkboxes['lui'].setChecked(not checked)

    def no_vshift_changed(self, checked):
        if self._loading:
            return
        self.checkboxes['vshift'].setChecked(not checked)

    def target_changed(self):
        if self._loading:
            return
        target = self.target_combo.currentData()
        self.state.target = target
        if target == 'logisim':
            self._select_profile('PF-08')
            self.state.rars = self.state.logisim = True
        elif target == 'cpu21':
            self._select_profile('cpu21')
            self.state.rars = self.state.logisim = False
        else:
            if self.state.baseline in ('cpu21', 'PF-08'):
                self._select_profile('PF-01')
            self.state.rars = False
            self.state.logisim = False
        self._sync_option_states()
        self.sync_capabilities()
        self.changed()
        self.set_status(f'目标已切换为 {target}；编译设置尚未运行')

    def rars_changed(self, checked):
        if self._loading:
            return
        if self.state.target == 'cpu21':
            self.rars_check.blockSignals(True); self.rars_check.setChecked(False); self.rars_check.blockSignals(False)
            return
        self.state.rars = bool(checked)
        self.changed()
        self.set_status('RARS 输出已启用' if checked else 'RARS 输出已关闭')

    def logisim_changed(self, checked):
        if self._loading:
            return
        if checked and self.state.target != 'logisim':
            idx = self.target_combo.findData('logisim')
            self.target_combo.setCurrentIndex(idx)
            return
        if checked:
            self.state.logisim = True
            self.state.rars = True
        self.changed()

    def output_changed(self, text):
        if self._loading:
            return
        self.state.output = text.strip()

    def write_output_changed(self, checked):
        if self._loading:
            return
        self.state.write_output = bool(checked)
        if checked and not self.state.output:
            self.set_status('已启用写盘，但还没有选择输出路径')
        else:
            self.set_status('编译成功后将写入输出路径' if checked else '编译后不自动写盘')

    def stack_changed(self, text):
        if not self._loading:
            self.state.stack_top = text.strip()

    def isa_file_changed(self, text):
        if self._loading:
            return
        self.state.isa_file = text.strip()
        self.sync_capabilities()
        self.changed()
        self.set_status('ISA 文件已更新，下次编译生效' if self.state.isa_file else '使用当前 profile')

    def dump_changed(self):
        if self._loading:
            return
        self.state.dumps = {key: cb.isChecked() for key, cb in self.dump_checks.items()}
        self.apply_dump_visibility()
        self.set_status('输出页显示选项已更新')

    def apply_dump_visibility(self):
        for index, title in enumerate(OUTPUT_TITLES):
            key = TAB_DUMP_KEYS.get(title)
            self.tabs.setTabVisible(index, title == '汇编' or (key is not None and self.state.dumps.get(key, True)))
        if not self.tabs.isTabVisible(self.tabs.currentIndex()):
            self.tabs.setCurrentIndex(0)

    def stats_changed(self, checked):
        if not self._loading:
            self.state.stats = bool(checked)

    def theme_changed(self):
        if self._loading:
            return
        self.apply_theme(self.theme_combo.currentData())

    def apply_theme(self, name, persist=True):
        if name not in model.THEME_NAMES:
            name = 'system'
        self.state.theme = name
        self.palette = theming.apply(QApplication.instance(), name)
        self.highlighter.set_palette(self.palette)
        self.highlight()
        for key, action in self.theme_actions.items():
            action.blockSignals(True)
            action.setChecked(key == name)
            action.blockSignals(False)
        if hasattr(self, 'theme_combo'):
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(name)))
            self.theme_combo.blockSignals(False)
        if hasattr(self, 'theme_label'):
            self.theme_label.setText(f'主题：{theming.resolve(name, QApplication.instance()).label}')
        if self.diag_rows:
            self.set_diagnostics(self.diag_rows)
        if persist:
            self.set_status(f'主题已切换为 {theming.resolve(name, QApplication.instance()).label}')

    # -------------------------------------------------------------- files/UI
    def update_numbers(self, *_):
        scroll = self.editor.verticalScrollBar().value()
        self.line_numbers.setPlainText('\n'.join(str(i) for i in range(1, self.editor.blockCount() + 1)))
        digits = max(3, len(str(max(1, self.editor.blockCount()))))
        self.line_numbers.setFixedWidth(max(46, self.editor.fontMetrics().horizontalAdvance('9') * digits + 18))
        self.line_numbers.verticalScrollBar().setValue(scroll)

    def highlight(self):
        if not hasattr(self, 'editor') or not hasattr(self, 'palette'):
            return
        selection = QTextEdit.ExtraSelection()
        selection.cursor = self.editor.textCursor()
        selection.cursor.clearSelection()
        selection.format.setBackground(QColor(self.palette.current_line))
        selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
        self.editor.setExtraSelections([selection])

    def zoom(self, amount):
        font = self.editor.font()
        size = font.pixelSize()
        if size <= 0:
            # The QSS/application font may be point-sized; use the rendered
            # pixel height so one zoom step is always visible.
            size = self.editor.fontMetrics().height()
        size = max(9, min(48, size + amount))
        font.setPixelSize(size)
        self.editor.setFont(font)
        self.editor.document().setDefaultFont(font)
        self.line_numbers.setFont(font)
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(' ') * 4)
        self.update_numbers()

    def update_position(self):
        if not hasattr(self, 'editor') or not hasattr(self, 'position_label'):
            return
        cursor = self.editor.textCursor()
        self.position_label.setText(f'Ln {cursor.blockNumber() + 1}, Col {cursor.positionInBlock() + 1}')

    def update_header(self):
        if not hasattr(self, 'file_label'):
            return
        name = '未命名' if self.state.path == '<untitled>' else Path(self.state.path).name
        dirty = '*' if hasattr(self, 'editor') and self.editor.document().isModified() else ''
        self.file_label.setText(f'{name}{dirty}')
        try:
            profile = model.profile_for_state(self.state)
            count = len(profile.instructions)
        except Exception:
            count = 0
        target = {'generic': 'GNU', 'cpu21': 'CPU21', 'logisim': 'Logisim'}.get(self.state.target, self.state.target)
        self.header_meta.setText(f'{target} · {self.state.baseline} · {count} 条指令')
        self.setWindowTitle(f'mycc {__version__} · {name}{dirty}')

    def set_status(self, text):
        self.status_text = text
        if hasattr(self, 'status_label') and not self.hovering:
            self.status_label.setText(text)

    def describe(self, text):
        self.hovering = bool(text)
        if hasattr(self, 'status_label'):
            self.status_label.setText('说明：' + text if text else self.status_text)

    def attach_hint(self, widget, text):
        if not text or not hasattr(self, 'hint_texts'):
            return
        widget.setToolTip(text)
        self.hint_texts[widget] = text
        widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.KeyPress and hasattr(self, 'palette'):
            modifiers = event.modifiers()
            if (modifiers & Qt.ControlModifier) and not (modifiers & (Qt.AltModifier | Qt.MetaModifier)):
                key = event.key()
                if key == Qt.Key_S and not (modifiers & Qt.ShiftModifier) and self.isActiveWindow():
                    # Handle Save here as well as through the QAction: when the
                    # completion popup owns the keyboard, the menu action may not
                    # receive the shortcut, but the application filter still sees it.
                    self.save_file()
                    return True
                if key in (Qt.Key_Plus, Qt.Key_Equal):
                    self.zoom(1); return True
                if key in (Qt.Key_Minus, Qt.Key_Underscore):
                    self.zoom(-1); return True
        if hasattr(self, 'hint_texts') and obj in self.hint_texts:
            if kind in (QEvent.Enter, QEvent.HoverEnter):
                self.describe(self.hint_texts[obj])
            elif kind in (QEvent.Leave, QEvent.HoverLeave):
                self.describe('')
        elif hasattr(self, 'tabs') and obj is self.tabs.tabBar():
            if kind in (QEvent.MouseMove, QEvent.HoverMove):
                index = self.tabs.tabBar().tabAt(event.pos())
                self.describe(TAB_HINTS[index] if 0 <= index < len(TAB_HINTS) else '')
            elif kind in (QEvent.Leave, QEvent.HoverLeave):
                self.describe('')
        return super().eventFilter(obj, event)

    def _tab_changed(self, index):
        if 0 <= index < len(TAB_HINTS):
            self.describe(TAB_HINTS[index])

    # ------------------------------------------------------------- file menu
    def confirm_discard(self):
        if not self.editor.document().isModified():
            return True
        answer = QMessageBox.question(self, '未保存的修改', '是否保存源文件？',
                                      QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if answer == QMessageBox.Save:
            return self.save_file()
        return answer == QMessageBox.Discard

    def new_file(self):
        if not self.confirm_discard():
            return
        self.state.path = '<untitled>'
        self.state.result = None
        self.state.last_asm = ''
        self.editor.setPlainText('')
        self.editor.document().setModified(False)
        self.set_diagnostics([])
        for view in self.outputs.values():
            view.clear()
        self.state.text = ''
        self.state.stale = False
        self.update_header()
        self.set_status('新建文件 · F5 编译')

    def open_file(self):
        if not self.confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, '打开 C 源文件', '', 'C 源文件 (*.c);;所有文件 (*)')
        if path:
            self.load_file(path)

    def load_file(self, path):
        try:
            data = Path(path).read_bytes()
            if len(data) > 128 * 1024:
                raise ValueError('源文件超过 128 KiB')
            text = data.decode('utf-8')
        except (OSError, UnicodeError, ValueError) as exc:
            QMessageBox.warning(self, '无法打开文件', str(exc))
            return False
        self.state.path = str(path)
        self.state.result = None
        self.state.last_asm = ''
        self.state.text = text
        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self.set_diagnostics([])
        for view in self.outputs.values():
            view.clear()
        self.update_header()
        self.set_status(f'已打开 {Path(path).name} · {len(text.splitlines())} 行')
        return True

    def save_file(self):
        if self.state.path == '<untitled>':
            return self.save_as()
        try:
            Path(self.state.path).write_text(self.editor.toPlainText(), encoding='utf-8')
            self.editor.document().setModified(False)
            self.state.text = self.editor.toPlainText()
            self.update_header()
            self.set_status(f'已保存 {Path(self.state.path).name}')
            return True
        except OSError as exc:
            QMessageBox.warning(self, '保存失败', str(exc))
            return False

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, '另存为', self.state.path if self.state.path != '<untitled>' else 'main.c',
                                              'C 源文件 (*.c);;所有文件 (*)')
        if not path:
            return False
        self.state.path = path
        return self.save_file()

    def export_current(self):
        index = self.tabs.currentIndex()
        if index < 0:
            return
        title = OUTPUT_TITLES[index] if index < len(OUTPUT_TITLES) else '输出'
        suffix = '.s' if title == '汇编' else ('.md' if title == 'Lowering 报告' else '.txt')
        path, _ = QFileDialog.getSaveFileName(self, '导出当前页', f'mycc{suffix}',
                                              '所有文件 (*)')
        if not path:
            return
        try:
            Path(path).write_text(self.tabs.widget(index).toPlainText(), encoding='utf-8')
            self.set_status(f'已导出 {path}')
        except OSError as exc:
            QMessageBox.warning(self, '导出失败', str(exc))

    def browse_output(self):
        resolved = model.output_file(self.state)
        initial = str(resolved) if resolved is not None else (self.state.output or '')
        path, _ = QFileDialog.getSaveFileName(
            self, '选择输出文件', initial, '汇编文件 (*.s *.asm);;所有文件 (*)')
        if path:
            self.output_edit.setText(path)

    def browse_output_dir(self):
        start = self.state.output
        if not start or (Path(start).exists() and Path(start).is_file()):
            start = str(Path(self.state.path).parent) if self.state.path not in ('', '<untitled>') else ''
        directory = QFileDialog.getExistingDirectory(self, '选择输出文件夹', start)
        if directory:
            self.output_edit.setText(directory)

    def browse_isa(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择 ISA JSON', '', 'JSON (*.json);;所有文件 (*)')
        if path:
            self.isa_file_edit.setText(path)

    # -------------------------------------------------------------- compile
    def start_compile(self):
        if self.worker is not None:
            return
        try:
            request = model.build_request(self.state)
            if self.state.target == 'logisim' or self.state.rars:
                model.stack_value(self.state)
        except (model.core.ProfileError, OSError, ValueError) as exc:
            self.set_status(f'配置错误：{exc}')
            QMessageBox.warning(self, '无法开始编译', str(exc))
            return
        self.state.text = self.editor.toPlainText()
        self.worker = Worker(request)
        self.worker.signals.finished.connect(self.finish_compile)
        self.worker.signals.failed.connect(self.compiler_failed)
        self.set_busy(True)
        self.set_status('正在编译…')
        self.pool.start(self.worker)

    def set_busy(self, busy):
        self.compile_action.setEnabled(not busy)
        self.cancel_action.setEnabled(busy)
        if hasattr(self, 'compile_button'):
            self.compile_button.setEnabled(not busy)
        if hasattr(self, 'cancel_button'):
            self.cancel_button.setEnabled(busy)

    def cancel_compile(self):
        if self.worker is not None:
            self.worker.cancel.set()
            self.set_status('正在取消编译…')

    def finish_compile(self, res):
        worker = self.worker
        if worker is None:
            return
        request = worker.request
        self.worker = None
        self.set_busy(False)
        snapshot = model.WorkbenchState(text=request.src.text, path=request.src.path)
        snapshot.last_asm = self.state.last_asm
        ui = model.apply_result(snapshot, res)
        try:
            current = model.build_request(self.state).profile
            stale = current.fingerprint != request.profile.fingerprint
        except (model.core.ProfileError, OSError, ValueError):
            stale = True
        self.state.result = res
        self.state.last_asm = snapshot.last_asm
        self.state.stale = stale
        self.outputs['汇编'].setPlainText(res.asm)
        self.outputs['Token'].setPlainText(model.core.dump_tokens(res))
        self.outputs['AST'].setPlainText(model.core.dump_ast(res))
        self.outputs['IR'].setPlainText(model.core.dump_ir(res))
        self.outputs['Lowering 报告'].setPlainText(model.core.dump_lowering_report(res))
        self.tabs.setTabText(0, '汇编 · 内容已过期' if stale else '汇编')
        self.set_diagnostics(ui.diag_rows)
        self.apply_dump_visibility()
        status = ui.status_line + (' · 配置已变化，请重新编译' if stale else '')
        if self.state.write_output and res.success:
            if not self.state.output:
                status += ' · 未设置输出路径'
            else:
                try:
                    paths = model.artifacts(self.state, request, res)
                    names = '、'.join(Path(path).name for path in paths[:4])
                    if len(paths) > 4:
                        names += f' 等 {len(paths)} 个'
                    status += f' · 已写入 {names}'
                except (OSError, ValueError, model.core.ProfileError) as exc:
                    status += f' · 写盘失败：{exc}'
                    QMessageBox.warning(self, '写盘失败', str(exc))
        if self.state.stats and res.stages_ms:
            status += ' · ' + ' / '.join(f'{k} {v:.1f}ms' for k, v in res.stages_ms.items())
        self.set_status(status)
        self.update_header()

    def compiler_failed(self, message):
        self.worker = None
        self.set_busy(False)
        self.set_status(f'编译异常：{message}')
        QMessageBox.critical(self, '编译失败', message)

    def set_diagnostics(self, diagnostics):
        self.diag_rows = list(diagnostics)
        self.diagnostics.setRowCount(0)
        for row, d in enumerate(self.diag_rows):
            self.diagnostics.insertRow(row)
            level = '错误' if d.severity == 'error' else '警告'
            values = [level, f'{d.line}:{d.col}', d.message, d.code]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if d.severity == 'error':
                    item.setForeground(QColor(self.palette.error))
                elif d.severity == 'warning':
                    item.setForeground(QColor(self.palette.warning))
                if col in (0, 2):
                    item.setToolTip(str(value))
                self.diagnostics.setItem(row, col, item)

    def jump(self, row, column=0):
        if not (0 <= row < len(self.diag_rows)):
            return
        d = self.diag_rows[row]
        block = max(0, min(d.line - 1, self.editor.blockCount() - 1))
        cursor = QTextCursor(self.editor.document().findBlockByNumber(block))
        cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, max(0, d.col - 1))
        self.editor.setTextCursor(cursor)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, max(1, d.end_col - d.col))
        selection = QTextEdit.ExtraSelection()
        selection.cursor = cursor
        selection.format.setBackground(QColor(self.palette.selection))
        self.editor.setExtraSelections([selection])
        self.editor.setFocus()

    # ------------------------------------------------------------- dialogs
    def show_command_preview(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('命令预览')
        dialog.resize(760, 280)
        layout = QVBoxLayout(dialog)
        info = QLabel('与当前 GUI 选项等价的命令行；复制到终端可复现同一产物。')
        info.setObjectName('Muted')
        layout.addWidget(info)
        view = QPlainTextEdit()
        view.setObjectName('CommandPreview')
        view.setReadOnly(True)
        view.setPlainText(model.command_text(self.state))
        layout.addWidget(view, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        copy = QPushButton('复制命令')
        copy.setObjectName('Primary')
        buttons.addButton(copy, QDialogButtonBox.ActionRole)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(view.toPlainText()))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def show_isa_details(self):
        try:
            texts = {'ISA 清单': model.isa_text(self.state, 'isa'),
                     '后端白名单': model.isa_text(self.state, 'whitelist')}
        except (model.core.ProfileError, OSError, ValueError) as exc:
            QMessageBox.warning(self, '无法读取 ISA', str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('ISA 详情')
        dialog.resize(820, 560)
        layout = QVBoxLayout(dialog)
        tabs = QTabWidget()
        for title, text in texts.items():
            view = QPlainTextEdit()
            view.setObjectName('OutputView')
            view.setReadOnly(True)
            view.setPlainText(text)
            tabs.addTab(view, title)
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def show_doctor(self):
        try:
            text = model.doctor_text()
        except Exception as exc:
            text = f'{type(exc).__name__}: {exc}'
        dialog = QDialog(self)
        dialog.setWindowTitle('环境自检')
        dialog.resize(760, 460)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setObjectName('CommandPreview')
        view.setReadOnly(True)
        view.setPlainText(text)
        layout.addWidget(view, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def show_cli_help(self):
        rows = ''.join(
            f'<tr><td><code>{flag}</code></td><td>{desc}</td><td>{where}</td></tr>'
            for flag, desc, where in CLI_SWITCHES)
        html = ('<h3>命令行开关与 GUI 对应</h3>'
                '<p>GUI 的构建选项可以生成等价命令；按 Ctrl+Shift+P 查看当前命令。</p>'
                '<table border="1" cellspacing="0" cellpadding="6" width="100%">'
                '<tr><th>开关</th><th>作用</th><th>GUI 位置</th></tr>'
                f'{rows}</table>')
        dialog = QDialog(self)
        dialog.setWindowTitle('CLI 开关对照')
        dialog.resize(920, 620)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setObjectName('OutputView')
        browser.setHtml(html)
        layout.addWidget(browser, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def show_about(self):
        QMessageBox.information(
            self, '关于 mycc',
            f'mycc {__version__}\nPySide6 {PySide6.__version__} / LGPL-3.0\n'
            f'当前主题：{theming.resolve(self.state.theme, QApplication.instance()).label}\n'
            '仅使用动态链接，源码分发。')

    def external_tools_help(self):
        QMessageBox.information(
            self, '外部工具与适配',
            '当前工作台可输出 GNU 汇编、RARS 单文件汇编或 Logisim ROM/RAM 镜像。\n\n'
            '软件辅助函数：runtime/runtime.s\n'
            '可选 QEMU：python -m tools.build SOURCE.c --qemu\n'
            'CPU21 示例：python -m tools.build SOURCE.c --target cpu21\n'
            'CPU21 配置及说明：adapters/cpu21/README.md\n'
            'RARS 目标：在构建与输出中勾选“RARS 单文件”，或使用 --target logisim 出镜像。\n'
            '外部命令仍建议在终端中显式执行。')

    def custom_instructions(self):
        try:
            current = model.profile_for_state(self.state)
        except (model.core.ProfileError, OSError, ValueError) as exc:
            QMessageBox.warning(self, '无法读取 ISA', str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('自定义指令')
        dialog.resize(520, 620)
        layout = QVBoxLayout(dialog)
        search = QLineEdit()
        search.setPlaceholderText('筛选指令…')
        layout.addWidget(search)
        listing = QListWidget()
        items = {}
        for name in sorted(model.core.ALL):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if current.has(name) else Qt.Unchecked)
            listing.addItem(item)
            items[name] = item
        layout.addWidget(listing, 1)
        search.textChanged.connect(lambda text: [items[name].setHidden(text.lower() not in name.lower())
                                                for name in items])
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return
        selected = {name for name, item in items.items() if item.checkState() == Qt.Checked}
        base = model.core.load_profile(self.state.baseline).instructions
        self.state.enable = [name for name in sorted(model.core.ALL) if name in selected and name not in base]
        self.state.disable = [name for name in sorted(model.core.ALL) if name not in selected and name in base]
        self.sync_capabilities()
        self.changed()
        self.set_status('自定义指令已更新，下次编译生效')

    def toggle_sidebar(self, checked):
        self.sidebar_scroll.setVisible(checked)
        if checked:
            self.sidebar_action.setChecked(True)

    def toggle_bottom(self, checked):
        self.diagnostics.setVisible(checked)
        self.tabs.setVisible(checked)
        if checked:
            self.bottom_action.setChecked(True)

    def closeEvent(self, event):
        if not self.confirm_discard():
            event.ignore()
            return
        self.cancel_compile()
        self.pool.waitForDone()
        model.save_settings(self.state)
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        event.accept()
