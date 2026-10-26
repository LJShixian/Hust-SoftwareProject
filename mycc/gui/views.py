"""Qt-only view layer. PySide6 6.8.3, LGPL-3.0; dynamically imported."""
from pathlib import Path
import os
import threading
import sys
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, QProcess, QTimer, Qt
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence, QTextCursor, QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPlainTextEdit, QTabWidget, QComboBox, QCheckBox, QLabel, QTableWidget,
    QTableWidgetItem, QFileDialog, QMessageBox, QAbstractItemView, QTextEdit, QLineEdit, QApplication)
from . import workbench as model


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
        self.state=model.WorkbenchState(); self.worker=None; self.process=None; self.commands=[]
        self.setWindowTitle('mycc · RISC-V 编译工作台'); self.resize(1200,850)
        self.pool=QThreadPool(self); self.pool.setMaxThreadCount(1)
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.timeout)
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
        pl.addWidget(QLabel('目标指令集'))
        self.profile=QComboBox()
        for i,name in enumerate(model.core.PRESETS,1): self.profile.addItem(f'PF-{i:02} · {name}',f'PF-{i:02}')
        self.profile.currentIndexChanged.connect(self.profile_changed); pl.addWidget(self.profile)
        self.checkboxes={}
        for name in ('mul','divrem','xor','cmpbr','byteload','auipc','lui','vshift'):
            cb=QCheckBox(name); self.checkboxes[name]=cb; cb.stateChanged.connect(self.capability_changed); pl.addWidget(cb)
        self.isa_summary=QLabel(); self.isa_summary.setWordWrap(True); pl.addWidget(self.isa_summary)
        pl.addWidget(QLabel('FPGA MMIO 地址（请按硬件填写）'))
        self.board_fields={}
        for key,title in [('uart_tx','串口 TX'),('vga_base','VGA 文本缓冲区'),('exit_status','退出状态寄存器')]:
            pl.addWidget(QLabel(title)); field=QLineEdit(self.state.board[key]); self.board_fields[key]=field
            field.setToolTip('支持 0x 十六进制或十进制；必须 4 字节对齐。只影响 FPGA 构建。')
            field.textChanged.connect(self.board_changed); pl.addWidget(field)
        pl.addStretch()
        top=QSplitter(); top.addWidget(source); top.addWidget(panel); top.setSizes([850,300])
        self.diagnostics=QTableWidget(0,4); self.diagnostics.setHorizontalHeaderLabels(['级别','位置','诊断码','消息'])
        self.diagnostics.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.diagnostics.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.diagnostics.horizontalHeader().setStretchLastSection(True)
        self.diagnostics.cellDoubleClicked.connect(self.jump)
        self.tabs=QTabWidget(); self.outputs={}
        for title in ('汇编','Token','AST','IR','Lowering 报告','运行输出','工具输出'):
            view=QPlainTextEdit(); view.setReadOnly(True); view.setFont(font)
            self.outputs[title]=view; self.tabs.addTab(view,title)
        vertical=QSplitter(Qt.Vertical); vertical.addWidget(top); vertical.addWidget(self.diagnostics); vertical.addWidget(self.tabs)
        vertical.setSizes([400,120,300]); self.setCentralWidget(vertical)
        toolbar=self.addToolBar('工作台')
        menus={name:self.menuBar().addMenu(name) for name in ('文件','编译','运行','视图','帮助')}
        def action(label,slot,key=None,menu='文件'):
            a=QAction(label,self); a.triggered.connect(slot)
            if key: a.setShortcut(QKeySequence(key))
            menus[menu].addAction(a)
            if label in ('新建','打开','保存','编译','取消编译','运行','终止','构建 FPGA','lint'): toolbar.addAction(a)
            return a
        action('新建',self.new_file,'Ctrl+N'); action('打开',self.open_file,'Ctrl+O')
        action('保存',self.save_file,'Ctrl+S'); action('另存为',self.save_as,'Ctrl+Shift+S')
        action('导出汇编',self.export_asm); action('导出诊断',self.export_diagnostics); action('导出 Lowering',self.export_lowering)
        self.compile_action=action('编译',self.start_compile,'F5','编译')
        action('取消编译',self.cancel_compile,menu='编译')
        action('运行',self.run_program,'F6','运行'); action('终止',self.stop_process,menu='运行')
        action('构建 FPGA',self.build_hardware,menu='编译')
        action('lint',self.lint,menu='编译')
        action('放大',lambda:self.zoom(1),'Ctrl++','视图'); action('缩小',lambda:self.zoom(-1),'Ctrl+-','视图')
        action('环境检查',self.doctor,menu='帮助')
        action('关于',lambda:QMessageBox.information(self,'mycc','mycc 0.1.0\nPySide6 6.8.3 / LGPL-3.0\n仅使用动态链接，源码分发。'),'','帮助')
        settings,message=model.load_settings()
        idx=self.profile.findData(settings['baseline']); self.profile.setCurrentIndex(max(0,idx))
        self.state.baseline=self.profile.currentData(); self.state.enable=settings['enable']; self.state.disable=settings['disable']
        if settings.get('board'):
            self.state.board=settings['board']
            for key,field in self.board_fields.items():
                field.blockSignals(True); field.setText(str(self.state.board[key])); field.blockSignals(False)
        self.sync_capabilities(); self.statusBar().showMessage(message or '就绪 · F5 编译，F6 运行')
        self.highlight()

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

    def board_changed(self):
        self.state.board={key:field.text() for key,field in self.board_fields.items()}
        try:
            model.board_arguments(self.state.board)
            self.statusBar().showMessage('MMIO 地址已修改，下次 FPGA 构建生效')
        except ValueError as exc: self.statusBar().showMessage(str(exc))

    def sync_capabilities(self):
        p=model.core.load_profile(self.state.baseline,self.state.enable,self.state.disable)
        for name,cb in self.checkboxes.items():
            cb.blockSignals(True); cb.setChecked(model.core.GROUPS[name]<=p.instructions); cb.blockSignals(False)
        self.isa_summary.setText(f'{len(p.instructions)} 条指令\nMV-ISA: 满足\n下次编译生效')

    def capability_changed(self):
        self.state.enable=[]; self.state.disable=[]
        for name,cb in self.checkboxes.items():
            (self.state.enable if cb.isChecked() else self.state.disable).append(name)
        self.sync_capabilities(); self.changed(); self.statusBar().showMessage('profile 已修改，下次编译生效')

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
            self.statusBar().showMessage(str(exc)); self.set_diagnostics([model.core.Diagnostic(str(path),1,1,'E-FILE-READ',str(exc),'lex')])

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

    def export(self,index,title,filter_):
        path,_=QFileDialog.getSaveFileName(self,title,'',filter_)
        if path:
            try: Path(path).write_text(model.export_asm_diag_lowering(self.state)[index],encoding='utf-8')
            except OSError as exc: QMessageBox.warning(self,title,str(exc))

    def export_asm(self): self.export(0,'导出汇编','Assembly (*.s)')
    def export_diagnostics(self): self.export(1,'导出诊断','Text (*.txt)')
    def export_lowering(self): self.export(2,'导出 Lowering','Markdown (*.md)')

    def start_compile(self):
        if self.worker: return
        try: request=model.build_request(self.state)
        except model.core.ProfileError as exc: self.statusBar().showMessage(str(exc)); return
        self.worker=Worker(request); self.worker.signals.finished.connect(self.finish_compile); self.worker.signals.failed.connect(self.compiler_failed)
        self.compile_action.setEnabled(False); self.statusBar().showMessage('正在编译…'); self.pool.start(self.worker)

    def cancel_compile(self):
        if self.worker: self.worker.cancel.set()

    def compiler_failed(self,message):
        self.worker=None; self.compile_action.setEnabled(True)
        QMessageBox.critical(self,'internal compiler error',message+'\n使用 python -m mycc source.c --profile '+self.state.baseline+' 复现')

    def finish_compile(self,res):
        request=self.worker.request; self.worker=None; self.compile_action.setEnabled(True)
        snapshot=model.WorkbenchState(text=request.src.text,path=request.src.path,last_asm=self.state.last_asm)
        ui=model.apply_result(snapshot,res)
        self.state.result=res; self.state.last_asm=ui.asm_text
        self.outputs['汇编'].setPlainText(ui.asm_text)
        for title,fn in [('Token',model.core.dump_tokens),('AST',model.core.dump_ast),('IR',model.core.dump_ir),('Lowering 报告',model.core.dump_lowering_report)]: self.outputs[title].setPlainText(fn(res))
        stale=self.state.text!=request.src.text or model.build_request(self.state).profile.fingerprint!=request.profile.fingerprint
        self.state.stale=ui.stale_flags or stale
        self.tabs.setTabText(0,'汇编 · 上次成功结果' if not res.success else '汇编 · 内容已过期' if stale else '汇编')
        self.set_diagnostics(ui.diag_rows); self.statusBar().showMessage(ui.status_line+(' · 内容已过期' if stale else ''))

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

    def start_commands(self,commands,tab):
        if self.process: self.statusBar().showMessage('已有任务在运行'); return
        self.commands=list(commands); self.process_tab=tab; self.outputs[tab].clear(); self.next_command()

    def next_command(self):
        if not self.commands: self.process=None; return
        args=self.commands.pop(0); out=self.outputs[self.process_tab]
        out.appendPlainText('> '+repr(args)); self.tabs.setCurrentWidget(out)
        self.process=QProcess(self); self.process.setWorkingDirectory(str(Path(__file__).resolve().parents[2]))
        proc=self.process
        self.process.readyReadStandardOutput.connect(lambda:out.appendPlainText(bytes(proc.readAllStandardOutput()).decode('utf-8',errors='replace')))
        self.process.readyReadStandardError.connect(lambda:out.appendPlainText(bytes(proc.readAllStandardError()).decode('utf-8',errors='replace')))
        self.process.finished.connect(self.process_finished); self.process.errorOccurred.connect(self.process_error)
        self.process.start(args[0],args[1:]); self.timer.start(30000)

    def process_error(self,_):
        if not self.process: return
        self.outputs[self.process_tab].appendPlainText('启动失败: '+self.process.errorString())
        self.timer.stop(); self.commands=[]; self.process.deleteLater(); self.process=None

    def process_finished(self,code,_):
        self.timer.stop(); self.outputs[self.process_tab].appendPlainText(f'退出码: {code}')
        if self.process: self.process.deleteLater(); self.process=None
        if code: self.commands=[]
        self.next_command()

    def timeout(self):
        self.stop_process(); self.outputs[self.process_tab].appendPlainText('已超时终止 (30 s)')

    def stop_process(self):
        self.commands=[]; self.timer.stop()
        if self.process: self.process.kill()

    def run_program(self):
        if not self.state.last_asm or self.state.stale: self.statusBar().showMessage('请先成功编译当前源码'); return
        root=Path(__file__).resolve().parents[2]; path=root/'build'/'workbench.s'; path.parent.mkdir(exist_ok=True)
        try: path.write_text(self.state.last_asm,encoding='utf-8')
        except OSError as exc: self.statusBar().showMessage(str(exc)); return
        self.start_commands(model.build_run_command(self.state,str(path)),'运行输出')

    def build_hardware(self):
        if not self.state.last_asm or self.state.stale: self.statusBar().showMessage('请先成功编译当前源码'); return
        try: model.board_arguments(self.state.board)
        except ValueError as exc: QMessageBox.warning(self,'MMIO 地址无效',str(exc)); return
        output,_=QFileDialog.getSaveFileName(self,'选择 FPGA 构建输出路径','build/firmware.elf','ELF (*.elf)')
        if not output: return
        source=Path(output).with_suffix('.s')
        try: source.write_text(self.state.last_asm,encoding='utf-8')
        except OSError as exc: QMessageBox.warning(self,'构建失败',str(exc)); return
        self.start_commands([model.build_hardware_command(self.state,str(source),output)],'工具输出')

    def lint(self):
        if not self.state.last_asm or self.state.stale: self.statusBar().showMessage('请先编译，再运行生成的 ELF 后执行 lint'); return
        path=Path(__file__).resolve().parents[2]/'build'/'workbench.s'; path.parent.mkdir(exist_ok=True)
        try: path.write_text(self.state.last_asm,encoding='utf-8')
        except OSError as exc: self.statusBar().showMessage(str(exc)); return
        commands=model.build_run_command(self.state)
        self.start_commands([commands[0],[sys.executable,'-m','tools.lint','build/workbench.elf','--profile',self.state.baseline,
            *[arg for x in self.state.enable for arg in ('--enable',x)],*[arg for x in self.state.disable for arg in ('--disable',x)],'--qemu']],'工具输出')

    def doctor(self): self.start_commands([[sys.executable,'-m','mycc','--doctor']],'工具输出')

    def closeEvent(self,event):
        if not self.confirm_discard(): event.ignore(); return
        self.cancel_compile(); self.pool.waitForDone(); self.stop_process()
        if self.process: self.process.waitForFinished(3000)
        model.save_settings(self.state); event.accept()
