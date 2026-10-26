# 目录整理记录

日期：2026-10-26。变更标识：CR-LAYOUT-001。基于 mycc 0.3.0；不改变产品范围或语言能力。

## 整理规则

保留 Python 模块位置和 `python -m` 接口；根目录保留 Windows 快捷入口。示例按普通编译与板卡分开，ISA 与 MMIO 分开，文档按规范、历史、证据分组。

## 路径对应

| 旧路径 | 新路径 |
|---|---|
| `bench/` 普通示例 | `examples/compiler/` |
| `bench/cpu21_*.c` | `examples/cpu21/` |
| `isa/PF-*.json` | `configs/isa/presets/` |
| `isa/board_v2.json` | `configs/isa/examples/board_v2.json` |
| `isa/board.example.json` | `adapters/generic/board.example.json` |
| `isa/hw_caps.json` | `adapters/cpu21/hw_caps.json` |
| 根目录 `.ps1` / `.sh` | `scripts/`；内部工作目录仍为仓库根目录 |
| `docs/SCOPE.md` | `docs/guides/scope.md` |
| `docs/SCOPE_IMPLEMENTATION.md` | `docs/history/0.3.0-scope.md` |
| `docs/CPU21_ADAPTATION.md` | `docs/history/0.2.0-cpu21.md` |
| `docs/FPGA_COMPATIBILITY.md` | `docs/history/0.1.0-fpga-audit.md` |
| `docs/IMPLEMENTATION.md` | `docs/history/0.1.0-initial.md` |
| `docs/workbench.png` | `docs/images/workbench.png` |
| 原“需求分析&软件设计文档”中的 SRS | `docs/specs/requirements/`，文件名保留版本号 |
| 原目录中的 SDD | `docs/specs/design/`，文件名保留版本号 |
| 原目录中的软件创意、决策纪要 | `docs/history/project-ideas.md`、`decisions.md` |
| 根目录 `.coverage` / `.pytest_cache` | 新运行写 `build/reports/.coverage` / `build/.pytest_cache/` |
| `build/coverage.json` | 新运行写 `build/reports/coverage.json` |

工具、测试及当前使用说明同步更新可执行引用；历史记录的旧路径文字保留，Markdown 导航随迁移修正，可用本表映射旧命令。

## 生成物

整理前 `build/` 内容及根目录覆盖率/pytest 缓存保留于 `build/archive/2026-10-26-before-layout/`，不纳入 Git。归档日志可能含旧绝对路径，复现请使用当前命令重新生成。`.venv/` 保持原位，Python 忽略缓存由 Python 管理。

历史验收 JSON 仍在 `docs/verification/`，未重写结果或哈希。

## 验证

常规检查为 115 passed、1 skipped，架构与覆盖率门槛通过。QEMU 缺失仍明确报告。迁移后 18 项 CPU21 固件回归通过，外部 81 个文件前后哈希相同，见 [本次验证记录](../verification/layout-results-2026-10-26.json)。验证器按名称选择普通或专用示例。Markdown 文件链接检查通过，README 的乘法切换示例及自定义 ISA 命令已实际编译核对。外部 FPGA 项目保持只读，所有输出写本仓库。
