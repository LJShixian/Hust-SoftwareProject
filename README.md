# mycc 0.3.0 — 可配置指令集的 C 子集编译器

输入 **受限 C 程序 + 可用 ISA**，输出 **GNU RISC-V 汇编 + 源码诊断 + 指令选择说明**。默认 generic/PF-01。编译核心与 CLI 仅需 Python 3.11+，图形工作台使用 PySide6。

[范围说明](docs/SCOPE.md) 是当前产品边界，先于程序调整提交为 `989e49d`。CPU21 固件适配和原有验证证据保留在独立适配层，主界面围绕编辑、编译和汇编查看组织。

[工作台预览](docs/workbench.png) · [本次范围收敛记录](docs/SCOPE_IMPLEMENTATION.md)

## 开始使用

```powershell
# 当前目录已准备 GUI 和测试虚拟环境
.\launch.cmd

# 编译器主流程，无需 GNU 工具链、板卡、QEMU 或 Vivado
python -m mycc bench/compiler_demo.c -o demo.s

# 同一源码启用硬件乘法，观察不同汇编和原因
python -m mycc bench/compiler_demo.c --enable mul -o demo-mul.s --dump-lowering-report

# 查看最终允许的指令
python -m mycc --dump-isa
python -m mycc --dump-isa-whitelist
```

全新环境可只使用标准库 CLI；GUI 与开发测试安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt pytest coverage
```

同时提供 PowerShell 与 Bash 入口；若 PowerShell 禁止执行脚本，使用 `.cmd` 即可，无需修改系统策略。

## 工作台与编译结果

主界面支持源码编辑、ISA 预设/组选择、F5 编译、取消、诊断双击定位和汇编导出（Ctrl+Shift+E）。标签页包含汇编、Token、AST、IR 和 Lowering 报告。失败保留上一次成功汇编并标记，编辑源码或 ISA 后标记过期。

全部合法 ISA 配置可选。`cpu21` 仅为一份硬件参考指令集合，选择它不会启用板卡启动、MMIO 或栈故障策略；启用字节加载也不会自动开放 char。

GUI 不启动外部构建/仿真进程，不显示板卡地址。帮助菜单提供外部命令说明。设置位于 `~/.config/mycc/gui.json`，格式为 schema_version=2；旧 board 配置保存在 legacy 字段中，不应用到普通编译。

### 汇编与运行时的边界

`.s` 是编译输出，不是独立可执行文件。函数 ABI、栈帧和表达式翻译由 mycc 负责；起始栈地址、最终内存布局、启动入口与外设由外部环境提供。

默认 PF-01 不含硬件乘除法，生成的 `__mulsi3/__divsi3/__modsi3` 等调用需链接 [runtime/runtime.s](runtime/runtime.s)。printint/printhex 的通用实现位于 `runtime/io.c`，putchar 和 exit 由外部运行时提供。只想观察编译结果时不需要链接它们。

输出使用 `.section`、`.type`、`%hi/%lo` 等 GNU 语法。**当前不宣称 RARS 兼容**；RARS 后端暂缓，第一阶段接已有 GNU 工具链。原完整扫雷继续由原项目 GCC 构建。

## ISA 与语言

`--profile` 选择预设；`--isa-file` 读取 JSON；`--enable/--disable` 接受指令或组、逗号列表和重复参数，disable 优先。兼容 `--no-lui`、`--no-vshift`。

| 预设 | 指令数 | 用途 |
|---|---:|---|
| PF-01 base | 26 | 默认 |
| PF-02 base-nolui | 25 | 无 lui 回退 |
| PF-03 base-novshift | 23 | 无寄存器移位回退 |
| PF-04 full-i | 32 | 便利指令组合 |
| PF-05 i+m | 29 | 硬件有符号乘除法组合 |
| PF-06 byteload | 30 | 能力描述，不开放 char |
| PF-07 all | 39 | 本编译器指令范围上限 |
| cpu21 | 32 | CPU21 的编译器相关参考 ISA |

支持 int、单层 int*、一维数组、最多 8 参数、函数递归、全局/局部变量、if/else、while/for、break/continue、return、算术/位运算/比较/短路、自增减、赋值、下标、取地址/解引用和 sizeof。

暂不支持预处理、字符串、char、unsigned/volatile、结构体、类型转换、函数指针、内联汇编、ISR、switch、?: 和 do-while，遇到时明确诊断。ISA 配置不改变这套语言范围。

可使用 `--dump-tokens/--dump-ast/--dump-ir/--dump-lowering-report/--stats` 观察结果。

## 开发验证

```powershell
.\check.cmd
```

检查包含核心演示、诊断/输出保护、GUI offscreen、真实 GNU 汇编/链接及 54 组合 ISA 矩阵，并断言原覆盖率门槛。缺少外部环境时报告跳过，不能据此声称执行通过。

三个核心演示位于 `bench/compiler_demo.c` 和 `tests/test_scope.py`：生成汇编、切换 mul 比较实现、制造错误观察位置和建议。

## 可选外部适配

这些命令需在终端显式执行，不是普通编译的依赖。

```powershell
# CPU21 固件与只读原始 RTL 验证
python -m tools.build bench/compiler_demo.c --target cpu21 -o build/cpu21-demo
.\check.cmd --cpu21 --fpga-root D:\Xilinx\Project\risc-v

# QEMU / GCC 验证，需要另行准备外部工具
python -m tools.build bench/compiler_demo.c --qemu
qemu-riscv32 build/compiler_demo.elf
python -m tools.compare bench/compiler_demo.c
```

[CPU21 适配](adapters/cpu21/README.md) 保留 Harvard 内存、启动、VGA、栈保护、MMIO 校验及 ROM 导出；数据在 `adapters/cpu21/board.json`、`isa.json`，代码资产也集中在该目录。兼容 `mycc --target cpu21`，由 CLI 显式加载适配并注入通用编译策略。不能把普通 generic 汇编直接当作 CPU21 完整固件。

[generic 裸机样例](adapters/generic/README.md) 的地址只是集成示例，默认构建不代表支持任意板卡。[QEMU 适配](adapters/qemu/README.md) 使用独立启动/链接资产。本机缺少 qemu-riscv32，QEMU/GCC 执行对照仍未验证。

工具不回写 `risc-v` 工程，不下载 FPGA。CPU21 的历史仿真结果与 0.3.0 回归分别记录；尚无物理上板证据。

## 目录与版本记录

```text
mycc/core/       七模块编译内核
mycc/cli.py      命令行文件与参数边界
mycc/gui/        薄编译工作台
runtime/        通用软件算术/内存和 I/O 格式函数
adapters/       CPU21、generic 裸机、QEMU 的可选外部环境
tools/          构建与开发验证工具
bench/, tests/  示例及测试
```

范围收敛记录为 CR-SCOPE-001，需求修订 SRS v1.4、设计修订 SDD v1.3。此前 0.2.0 / CR-CPU21-001 的实现、文档和验收作为历史保留，当前默认行为以范围说明和最新修订为准。
