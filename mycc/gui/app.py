"""Lazy Qt entry point with a clean CLI fallback."""
import os
import subprocess
import sys


def launch(path=None):
    if os.name!='nt' and sys.platform!='darwin' and not any(os.environ.get(k) for k in ('DISPLAY','WAYLAND_DISPLAY')) and os.environ.get('QT_QPA_PLATFORM')!='offscreen':
        print('mycc: 图形环境不可用，请使用 python -m mycc file.c -o out.s',file=sys.stderr)
        return 64
    try:
        from PySide6.QtWidgets import QApplication
        from .views import MainWindow
    except ImportError:
        print('mycc: PySide6 未安装，请安装 requirements.txt；CLI 仍可使用',file=sys.stderr)
        return 64
    try:
        probe=subprocess.run([sys.executable,'-c','from PySide6.QtWidgets import QApplication; a=QApplication([])'],
                              capture_output=True,timeout=10)
        if probe.returncode:
            print('mycc: Qt 平台插件不可用，请修复 PySide6 环境；CLI 仍可使用',file=sys.stderr)
            return 64
    except (OSError,subprocess.TimeoutExpired):
        print('mycc: 图形环境启动检查失败，请使用 CLI',file=sys.stderr)
        return 64
    app=QApplication.instance() or QApplication(sys.argv[:1])
    window=MainWindow()
    if path: window.load_file(path)
    window.show()
    return app.exec()
