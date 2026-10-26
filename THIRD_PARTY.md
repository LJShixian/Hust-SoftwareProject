# Third-party components

- Compiler core and CLI: Python standard library only.
- Optional GUI: PySide6 6.8.3 and its Qt/Shiboken wheel dependencies, installed dynamically from upstream wheels. PySide6 is distributed under LGPLv3/GPLv3/commercial licensing; retain upstream license notices in installed wheels. This repository does not bundle Qt binaries, freeze applications, or modify PySide6.
- Test tools: pytest and coverage.py; development dependencies only.
- Target tools: external GNU RISC-V binutils/GCC and QEMU, not bundled.

Upstream licensing information: https://doc.qt.io/qtforpython-6/licenses.html
