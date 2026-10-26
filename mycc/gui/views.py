"""Qt-only view layer. PySide6 6.8.3, LGPL-3.0; dynamically imported."""
from pathlib import Path
import os
import threading
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Qt, QEvent
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence, QTextCursor, QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPlainTextEdit, QTabWidget, QComboBox, QCheckBox, QLabel, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QAbstractItemView, QTextEdit, QApplication, QScrollArea,
    QMenu)
from . import workbench as model


# Hover text. Shown in the status bar so a first-time user can ask "what is Token?"
# without reading the README. Also installed as a native tooltip.
ACTION_HINTS = {
    '新建': '清空编辑器，新建一个未命名的源文件（会先询问是否保存当前修改）',
    '打开': '打开一个 .c 源文件；上限 128 KiB，按 UTF-8 解码',
    '保存': '把编辑器内容写回源文件；未命名时等同于另存为',
    '另存为': '选择新路径保存当前源码',
    '导出当前页…': '把下方当前选中的输出页存成文件：汇编存 .s，Lowering 报告存 .md，其余存 .txt',
    '编译': '按右侧 ISA 配置编译（F5）。编译失败时不会覆盖上一次成功的汇编',
    '取消编译': '中止正在进行的编译；只在编译过程中可用',
    '放大': '放大编辑器字号（只影响显示，不影响产物）',
    '缩小': '缩小编辑器字号（只影响显示，不影响产物）',
    '关于': '版本号与第三方组件许可说明',
    '外部工具与适配说明': '如何用外部工具链把生成的汇编变成可执行文件或板卡镜像',
}

TAB_HINTS = [
    '汇编：最终生成的 GNU RISC-V 汇编。这是唯一要交给 as/ld 的产物，按 Ctrl+Shift+E 可存成 .s',
    'Token：词法分析结果（行:列、记号类别、原文）。语法报错时先看这里，确认关键字、数字、注释有没被正确切开',
    'AST：语法树，每个节点带 @行:列。用来核对运算符优先级、括号配对、if/else 归属是否符合预期',
    'IR：代码生成期间记录的操作序列（CONST32、BIN_MUL、CALL 等）。它是结构化记录，不是独立优化器的中间表示',
    'Lowering 报告：每个“缺指令”决策的明细——源码位置、选中的实现、因缺能力被拒的方案、代价增量 Δ。想知道“为什么代码变长了”就看这一页',
]

OUTPUT_TITLES = ['汇编', 'Token', 'AST', 'IR', 'Lowering 报告']

GROUP_HINTS = {
    'mul': '硬件乘法（M 扩展 mul）。取消勾选则改调软件乘法 __mulsi3，每处多 2 条指令',
    'divrem': '硬件除法与取余（div / rem）。取消勾选则调 __divsi3 / __modsi3',
    'xor': '硬件按位异或。取消勾选则用 (a|b)-(a&b) 三条指令合成',
    'cmpbr': '额外的比较分支（bge / bgeu / bltu / sltiu）。取消勾选则用 blt 组合回退',
    'byteload': '字节与半字加载（lb / lbu / lh / lhu）。注意：语言本身仍不支持 char，这项只是预留能力',
    'auipc': 'PC 相对高位加载（auipc）。取消勾选则改用 jal 取 PC 的方式算地址',
    'lui': '立即数高位加载。最影响代码长度的一项：取消勾选后大常量和全局地址要走“字节合成”，每处多 7 条指令',
    'vshift': '寄存器移位（sll / srl / sra）。取消勾选则移位改调软件辅助函数',
}

PRESET_HINT = ('选择一组预定义的指令集，默认 PF-01（26 条）。cpu21 是某块板子的参考集合，'
               '选中它不会自动切换板卡的启动与地址约定')


class Signals(QObject):
    finished=Signal(object)
    failed=Signal(str)


class Worker(QRunnable):
    def __init__(self,request):
        super().__init__(); self.request=request; self.signals=Signals()
        self.cancel=threading.Event()

    def run(self):
        try:
            req=self.request; req.options.cancelled=self.cancel.is_set
            res=model.core.compile(req.src,req.profile,options=req.options)
            self.signals.finished.emit(res)
        except Exception as exc: self.signals.failed.emit(f'{type(exc).__name__}: {exc}')


class Highlighter(QSyntaxHighlighter):
    def highlightBlock(self,text):
        import re
        for pattern,color in [(r'\b(int|void|if|else|while|for|return|break|continue|sizeof)\b','#2266bb'),
                              (r'\b(0[xX][0-9a-fA-F]+|[0-9]+)\b','#986800'),
                              (r'//.*$','#548353')]:
            fmt=QTextCharFormat(); fmt.setForeground(QColor(color))
            for m in re.finditer(pattern,text): self.setFormat(m.start(),len(m.group()),fmt)
        comment=QTextCharFormat(); comment.setForeground(QColor('#548353'))
        start=0 if self.previousBlockState()==1 else text.find('/*')
        self.setCurrentBlockState(0)
        while start>=0:
            end=text.find('*/',start+2)
            if end<0:
                self.setFormat(start,len(text)-start,comment); self.setCurrentBlockState(1); break
            self.setFormat(start,end+2-start,comment); start=text.find('/*',end+2)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Qt's Windows offscreen plugin may expose an empty font database.
        # Register installed system fonts in that case; no fonts are bundled.
        if os.name=='nt' and not QFontDatabase.families():
            fontdir=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
            for name in ('consola.ttf','msyh.ttc','segoeui.ttf'):
                QFontDatabase.addApplicationFont(str(fontdir/name))
            QApplication.setFont(QFont('Microsoft YaHei',10))
        self.state=model.WorkbenchState(); self.worker=None
        self.setWindowTitle('mycc · RISC-V 编译工作台'); self.resize(1200,850)
        self.pool=QThreadPool(self); self.pool.setMaxThreadCount(1)
        # Status line doubles as the hover-help surface: `status_text` is the resting
        # message, `describe()` temporarily replaces it while the pointer is on a
        # control. Discoverability hint sits on the right, out of the way.
        self.hint_texts={}; self.hovering=False; self.status_text=''
        self.status_label=QLabel(); self.status_label.setContentsMargins(6,0,0,0)
        self.statusBar().addWidget(self.status_label,1)
        self.statusBar().addPermanentWidget(QLabel('将鼠标停在按钮或页签上可查看该功能说明'))
        font=QFont('Consolas',11)
        self.editor=QPlainTextEdit(); self.editor.setFont(font); self.editor.setPlainText(self.state.text)
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(' ')*4)
        self.highlighter=Highlighter(self.editor.document())
        self.editor.document().setModified(False)
        self.editor.textChanged.connect(self.changed)
        self.editor.cursorPositionChanged.connect(self.highlight)
        self.line_numbers=QPlainTextEdit(); self.line_numbers.setReadOnly(True); self.line_numbers.setFont(font)
        self.line_numbers.setFixedWidth(65); self.line_numbers.setFocusPolicy(Qt.NoFocus)
        self.line_numbers.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.line_numbers.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.line_numbers.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.verticalScrollBar().valueChanged.connect(self.line_numbers.verticalScrollBar().setValue)
        self.editor.blockCountChanged.connect(self.update_numbers); self.update_numbers()
        source=QWidget(); source_layout=QHBoxLayout(source); source_layout.setContentsMargins(0,0,0,0)
        source_layout.addWidget(self.line_numbers); source_layout.addWidget(self.editor)
        panel=QWidget(); pl=QVBoxLayout(panel)
        note=QLabel('C 子集 → GNU RISC-V 汇编\n选择可用指令，查看生成代码和回退原因\nISA 选择不改变 C 子集的支持范围')
        note.setWordWrap(True); pl.addWidget(note)
        pl.addWidget(QLabel('可用指令集'))
        self.profile=QComboBox()
        for i,name in enumerate(model.core.PRESETS,1):
            value='cpu21' if name=='cpu21' else f'PF-{i:02}'
            self.profile.addItem('cpu21 · 硬件参考 ISA' if name=='cpu21' else f'PF-{i:02} · {name}',value)
        self.profile.currentIndexChanged.connect(self.profile_changed); pl.addWidget(self.profile)
        self.attach_hint(self.profile,PRESET_HINT)
        self.checkboxes={}
        for name in ('mul','divrem','xor','cmpbr','byteload','auipc','lui','vshift'):
            cb=QCheckBox(name); self.checkboxes[name]=cb; cb.stateChanged.connect(self.capability_changed); pl.addWidget(cb)
            self.attach_hint(cb,GROUP_HINTS[name])
        self.isa_summary=QLabel(); self.isa_summary.setWordWrap(True); pl.addWidget(self.isa_summary)
        pl.addStretch()
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(panel); scroll.setMinimumWidth(300)
        top=QSplitter(); top.addWidget(source); top.addWidget(scroll); top.setSizes([850,330])
        self.diagnostics=QTableWidget(0,4); self.diagnostics.setHorizontalHeaderLabels(['级别','位置','诊断码','消息'])
        self.diagnostics.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.diagnostics.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.diagnostics.horizontalHeader().setStretchLastSection(True)
        self.diagnostics.cellDoubleClicked.connect(self.jump)
        self.tabs=QTabWidget(); self.outputs={}
        for index,title in enumerate(OUTPUT_TITLES):
            view=QPlainTextEdit(); view.setReadOnly(True); view.setFont(font)
            self.outputs[title]=view; self.tabs.addTab(view,title)
            self.tabs.setTabToolTip(index,TAB_HINTS[index])
        self.tabs.tabBar().installEventFilter(self)
        self.tabs.tabBar().setMouseTracking(True)
        vertical=QSplitter(Qt.Vertical); vertical.addWidget(top); vertical.addWidget(self.diagnostics); vertical.addWidget(self.tabs)
        vertical.setSizes([520,110,270]); self.setCentralWidget(vertical)
        # No toolbar: every command lives in exactly one place (the menu bar).
        # A toolbar repeating 新建/打开/保存/编译 was pure duplication for an
        # app this size, and the shortcuts (Ctrl+N/O/S, F5, Ctrl+Shift+E) already
        # give the same one-keystroke access.
        # Menus are built explicitly with `self` as parent and kept on `self`.
        # QMenuBar.addMenu(str) hands shiboken ownership of the returned wrapper, so a
        # transient wrapper (e.g. from QAction.menu()) being collected can delete the
        # C++ QMenu out from under the window.
        self.menus={}
        for name in ('文件','构建','视图','帮助'):
            menu=QMenu(name,self); self.menuBar().addMenu(menu); self.menus[name]=menu
        menus=self.menus
        def action(label,slot,key=None,menu='文件',hint=''):
            a=QAction(label,self); a.triggered.connect(slot)
            if key: a.setShortcut(QKeySequence(key))
            if hint:
                a.setStatusTip(hint); a.setToolTip(hint)
                # Menu items have no widget to filter, so the hover hook comes from
                # the action itself; aboutToHide restores the resting message.
                a.hovered.connect(lambda text=hint: self.describe(text))
            menus[menu].addAction(a)
            return a
        action('新建',self.new_file,'Ctrl+N',hint=ACTION_HINTS['新建'])
        action('打开',self.open_file,'Ctrl+O',hint=ACTION_HINTS['打开'])
        action('保存',self.save_file,'Ctrl+S',hint=ACTION_HINTS['保存'])
        action('另存为',self.save_as,'Ctrl+Shift+S',hint=ACTION_HINTS['另存为'])
        action('导出当前页…',self.export_current,'Ctrl+Shift+E',hint=ACTION_HINTS['导出当前页…'])
        self.compile_action=action('编译',self.start_compile,'F5','构建',ACTION_HINTS['编译'])
        self.cancel_action=action('取消编译',self.cancel_compile,menu='构建',hint=ACTION_HINTS['取消编译'])
        action('放大',lambda:self.zoom(1),'Ctrl++','视图',ACTION_HINTS['放大'])
        action('缩小',lambda:self.zoom(-1),'Ctrl+-','视图',ACTION_HINTS['缩小'])
        action('关于',lambda:QMessageBox.information(self,'mycc','mycc 0.3.0\nPySide6 6.8.3 / LGPL-3.0\n仅使用动态链接，源码分发。'),'','帮助',ACTION_HINTS['关于'])
        action('外部工具与适配说明',self.external_tools_help,menu='帮助',hint=ACTION_HINTS['外部工具与适配说明'])
        # Cancel is meaningful only while a compile is running, so it starts
        # disabled instead of being permanently visible-but-dead.
        self.cancel_action.setEnabled(False)
        for menu in self.menus.values(): menu.aboutToHide.connect(lambda: self.describe(''))
        settings,message=model.load_settings()
        idx=self.profile.findData(settings['baseline']); self.profile.setCurrentIndex(max(0,idx))
        self.state.baseline=self.profile.currentData()
        self.state.enable,self.state.disable=model.normalize_capabilities(
            self.state.baseline,settings['enable'],settings['disable'])
        self.state.legacy=settings['legacy']
        self.sync_capabilities(); self.set_status(message or '就绪 · F5 编译，Ctrl+Shift+E 导出当前页')
        self.highlight()

    # ---- hover help ------------------------------------------------------
    def attach_hint(self,widget,text):
        """Show `text` in the status bar while the pointer rests on `widget`."""
        if not text: return
        widget.setToolTip(text); self.hint_texts[widget]=text
        widget.installEventFilter(self)

    def set_status(self,text):
        """Resting status message; hover text temporarily overlays it."""
        self.status_text=text
        if not self.hovering: self.status_label.setText(text)

    def describe(self,text):
        self.hovering=bool(text)
        # Prefix is plain Chinese so the string survives any console/codepage when
        # the status text is logged; symbols like U+24D8 are not in GBK.
        self.status_label.setText('说明：'+text if text else self.status_text)

    def eventFilter(self,obj,event):
        kind=event.type()
        if obj in self.hint_texts:
            if kind in (QEvent.Enter,QEvent.HoverEnter): self.describe(self.hint_texts[obj])
            elif kind in (QEvent.Leave,QEvent.HoverLeave): self.describe('')
        elif obj is self.tabs.tabBar():
            # Tabs carry no QAction, so the per-tab help is resolved from the
            # pointer position instead of a statusTip. The bar has mouse tracking
            # on, otherwise Move events only arrive while a button is held.
            if kind in (QEvent.MouseMove,QEvent.HoverMove):
                index=self.tabs.tabBar().tabAt(event.pos())
                self.describe(TAB_HINTS[index] if 0<=index<len(TAB_HINTS) else '')
            elif kind in (QEvent.Leave,QEvent.HoverLeave): self.describe('')
        return super().eventFilter(obj,event)

    def update_numbers(self,*_):
        scroll=self.editor.verticalScrollBar().value()
        self.line_numbers.setPlainText('\n'.join(str(i) for i in range(1,self.editor.blockCount()+1)))
        self.line_numbers.verticalScrollBar().setValue(scroll)

    def highlight(self):
        selection=QTextEdit.ExtraSelection(); selection.cursor=self.editor.textCursor(); selection.cursor.clearSelection()
        selection.format.setBackground(QColor('#edf3fa')); selection.format.setProperty(QTextCharFormat.FullWidthSelection,True)
        self.editor.setExtraSelections([selection])

    def zoom(self,amount):
        self.editor.zoomIn(amount); self.line_numbers.zoomIn(amount)

    def changed(self):
        self.state.text=self.editor.toPlainText(); self.state.stale=True
        if self.state.last_asm: self.tabs.setTabText(0,'汇编 · 内容已过期')

    def profile_changed(self):
        self.state.baseline=self.profile.currentData(); self.state.enable=[]; self.state.disable=[]; self.sync_capabilities()
        self.changed()

    def sync_capabilities(self):
        p=model.core.load_profile(self.state.baseline,self.state.enable,self.state.disable)
        for name,cb in self.checkboxes.items():
            cb.blockSignals(True); cb.setChecked(model.core.GROUPS[name]<=p.instructions); cb.blockSignals(False)
        self.isa_summary.setText(f'{len(p.instructions)} 条指令 · MV-ISA 满足\n指令数变化在下次编译时体现')

    def capability_changed(self):
        enabled=[name for name,cb in self.checkboxes.items() if cb.isChecked()]
        disabled=[name for name,cb in self.checkboxes.items() if not cb.isChecked()]
        # Keep only what actually differs from the preset; see
        # workbench.normalize_capabilities for why the raw lists are wrong.
        self.state.enable,self.state.disable=model.normalize_capabilities(
            self.state.baseline,enabled,disabled)
        self.sync_capabilities(); self.changed(); self.set_status('profile 已修改，下次编译生效')

    def confirm_discard(self):
        if not self.editor.document().isModified(): return True
        answer=QMessageBox.question(self,'未保存的修改','是否保存源文件？',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        if answer==QMessageBox.Save: return self.save_file()
        return answer==QMessageBox.Discard

    def new_file(self):
        if self.confirm_discard():
            self.state.path='<untitled>'; self.editor.setPlainText(''); self.editor.document().setModified(False)

    def open_file(self):
        path,_=QFileDialog.getOpenFileName(self,'打开 C 文件','','C source (*.c)')
        if path and self.confirm_discard(): self.load_file(path)

    def load_file(self,path):
        try:
            data=Path(path).read_bytes()
            if len(data)>128*1024: raise ValueError('文件超过 128 KiB')
            text=data.decode('utf-8-sig')
            self.state.path=str(path); self.editor.setPlainText(text); self.editor.document().setModified(False)
            self.setWindowTitle(f'mycc · {Path(path).name}')
        except (OSError,UnicodeError,ValueError) as exc:
            self.set_status(str(exc)); self.set_diagnostics([model.core.Diagnostic(str(path),1,1,'E-FILE-READ',str(exc),'lex')])

    def save_file(self):
        if self.state.path=='<untitled>': return self.save_as()
        try:
            Path(self.state.path).write_text(self.editor.toPlainText(),encoding='utf-8')
            self.editor.document().setModified(False); return True
        except OSError as exc: QMessageBox.warning(self,'保存失败',str(exc)); return False

    def save_as(self):
        path,_=QFileDialog.getSaveFileName(self,'保存 C 文件','','C source (*.c)')
        if not path: return False
        old=self.state.path; self.state.path=path
        if self.save_file(): return True
        self.state.path=old; return False

    EXPORT_FILTERS={'汇编':('Assembly (*.s)','.s'),'Lowering 报告':('Markdown (*.md)','.md')}

    def export_current(self):
        """Export whichever output tab is in front; one command replaces three."""
        title=OUTPUT_TITLES[self.tabs.currentIndex()]
        text=self.outputs[title].toPlainText()
        if not text.strip():
            self.set_status(f'{title} 页还没有内容，先按 F5 编译'); return
        pattern,_=self.EXPORT_FILTERS.get(title,('Text (*.txt)','.txt'))
        path,_=QFileDialog.getSaveFileName(self,f'导出{title}','',pattern)
        if not path: return
        try:
            Path(path).write_text(text,encoding='utf-8'); self.set_status(f'已导出 {title} → {path}')
        except OSError as exc: QMessageBox.warning(self,f'导出{title}',str(exc))

    def set_busy(self,busy):
        """Compile and cancel are mutually exclusive, so only one is ever enabled."""
        self.compile_action.setEnabled(not busy); self.cancel_action.setEnabled(busy)

    def start_compile(self):
        if self.worker: return
        try: request=model.build_request(self.state)
        except model.core.ProfileError as exc: self.set_status(str(exc)); return
        self.worker=Worker(request); self.worker.signals.finished.connect(self.finish_compile); self.worker.signals.failed.connect(self.compiler_failed)
        self.set_busy(True); self.set_status('正在编译…'); self.pool.start(self.worker)

    def cancel_compile(self):
        if self.worker: self.worker.cancel.set()

    def compiler_failed(self,message):
        self.worker=None; self.set_busy(False)
        QMessageBox.critical(self,'internal compiler error',message+'\n使用 python -m mycc source.c --profile '+self.state.baseline+' 复现')

    def finish_compile(self,res):
        request=self.worker.request; self.worker=None; self.set_busy(False)
        snapshot=model.WorkbenchState(text=request.src.text,path=request.src.path,last_asm=self.state.last_asm)
        ui=model.apply_result(snapshot,res)
        self.state.result=res; self.state.last_asm=ui.asm_text
        self.outputs['汇编'].setPlainText(ui.asm_text)
        for title,fn in [('Token',model.core.dump_tokens),('AST',model.core.dump_ast),('IR',model.core.dump_ir),('Lowering 报告',model.core.dump_lowering_report)]: self.outputs[title].setPlainText(fn(res))
        stale=self.state.text!=request.src.text or model.build_request(self.state).profile.fingerprint!=request.profile.fingerprint
        self.state.stale=ui.stale_flags or stale
        self.tabs.setTabText(0,'汇编 · 上次成功结果' if not res.success else '汇编 · 内容已过期' if stale else '汇编')
        self.set_diagnostics(ui.diag_rows); self.set_status(ui.status_line+(' · 内容已过期' if stale else ''))

    def set_diagnostics(self,rows):
        self.diag_rows=rows; self.diagnostics.setRowCount(len(rows))
        for row,d in enumerate(rows):
            for col,value in enumerate([d.severity,f'{d.line}:{d.col}',d.code,d.message]): self.diagnostics.setItem(row,col,QTableWidgetItem(value))

    def jump(self,row,_):
        d=self.diag_rows[row]; cursor=self.editor.textCursor()
        cursor.setPosition(model.source_offset(self.state.text,d.line,d.col)); self.editor.setTextCursor(cursor); self.editor.setFocus()
        selection=QTextEdit.ExtraSelection(); selection.cursor=cursor
        selection.cursor.movePosition(QTextCursor.Right,QTextCursor.KeepAnchor,max(1,d.end_col-d.col))
        selection.format.setBackground(QColor('#ffcccc')); self.editor.setExtraSelections([selection])

    def external_tools_help(self):
        QMessageBox.information(self,'外部工具与适配',
            '当前工作台输出 GNU 汇编；最终地址、启动和外设由外部工具链提供。\n\n'
            '软件辅助函数：runtime/runtime.s\n'
            '可选 QEMU：python -m tools.build SOURCE.c --qemu\n'
            'CPU21 示例：python -m tools.build SOURCE.c --target cpu21\n'
            'CPU21 配置及说明：adapters/cpu21/README.md\n\n'
            'RARS 格式兼容与完整扫雷暂缓。外部命令需在终端中显式执行。')

    def closeEvent(self,event):
        if not self.confirm_discard(): event.ignore(); return
        self.cancel_compile(); self.pool.waitForDone()
        model.save_settings(self.state); event.accept()
