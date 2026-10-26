# mycc — 可配置 RISC-V C 子集编译器

根据目录中的 **SRS-MYCC-001 v1.2** 和 **SDD-MYCC-001 v1.1** 实现。Python 3.11+，编译内核和 CLI 仅依赖标准库，图形工作台使用 PySide6。编译结果为 RV32 汇编，GNU 工具链负责汇编、链接和导出固件。

[查看工作台预览](docs/workbench.png)。

## Windows 快速开始

当前工作目录已创建 `.venv` 并安装 GUI 与测试依赖。

```powershell
# 打开图形工作台
.\launch.cmd

# 编译一个 C 文件，无需 GUI 或第三方包
python -m mycc bench/hello.c -o hello.s

# 构建 FPGA 固件：需要 RISC-V GNU 工具链在 PATH 中
python -m tools.build bench/hello.c --profile PF-01

# 一键检查（使用本项目虚拟环境）
.\check.cmd
```

全新环境安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt pytest coverage
```

纯 CLI 无需安装任何包；`python -m mycc --doctor` 检查依赖。离线 GUI 安装可提前下载 wheel，然后执行 `python -m pip install --no-index --find-links wheels -r requirements.txt`。

## 按实际硬件填写地址

工作台右侧提供 **串口 TX、VGA 文本缓冲区、退出状态寄存器** 地址输入框。先按 F5 编译，再点 **构建 FPGA** 选择输出路径。三项地址随设置保存，更改地址后重新构建即可。

命令行提供相同能力，接受十六进制或十进制，校验 32 位范围和 4 字节对齐：

```powershell
python -m tools.build bench/hello.c --profile PF-05 --uart-tx 0x30000000 --vga-base 0x30001000 --exit-status 0x30000008 -o build/myboard

# 或保存板卡配置，命令行单项参数覆盖配置文件
python -m tools.build bench/hello.c --board-file isa/board.example.json --uart-tx 0x30000000
```

输出 `.s`、`.elf`、`.bin`、Verilog/readmemh `.hex` 和 Logisim v2 原始字节 `.logisim.hex`；保留 `.o` 与运行时中间产物。地址通过链接符号绑定，生成固件中的实际数值随配置变化，已用 GNU `nm` 和二进制检查验证。

**示例 MMIO 地址是占位配置，不是已确认的硬件地址。** 链接布局目前为 IMEM `0x0000..0x7FFF`、DMEM `0x8000..0xBFFF`，栈顶 `0xC000`；如硬件内存映射不同，修改 `linker/link.ld`。VGA 运行时采用 80×25、每字符一个 32 位字的缓冲格式，支持换行和回绕；串口通过 32 位寄存器写入字符低字节。需与实际外设协议一致。

## ISA 与观察编译过程

```powershell
python -m mycc --dump-isa --profile PF-01
python -m mycc --dump-isa-whitelist --profile PF-01
python -m mycc bench/muldiv.c -o build/soft.s --dump-lowering-report
python -m mycc bench/muldiv.c -o build/hard.s --enable m
python -m mycc bench/shifts.c -o build/fallback.s --disable lui,vshift
python -m mycc bench/arrays.c -o build/custom.s --isa-file isa/board_v2.json
```

可用 `--dump-tokens`、`--dump-ast`、`--dump-ir`、`--dump-lowering-report`、`--stats`。`--enable/--disable` 支持组名或指令名，以逗号分隔，可重复使用；disable 优先。兼容 `--no-lui`、`--no-vshift`。

| Profile | 名称 | 实际指令数 |
|---|---|---:|
| PF-01 | base | 26 |
| PF-02 | base-nolui | 25 |
| PF-03 | base-novshift | 23 |
| PF-04 | full-i | 32 |
| PF-05 | i+m | 29 |
| PF-06 | byteload | 30 |
| PF-07 | all | 39 |

数量按文档给出的集合计算；原文 PF-04/PF-07 的计数矛盾见 [实现与验证记录](docs/IMPLEMENTATION.md)。ISA 配置文件与 MMIO 地址文件是两种不同格式，示例分别为 `isa/board_v2.json` 与 `isa/board.example.json`。`isa/hw_caps.json` 仅为示例能力清单，应由硬件侧实际导出替换。

## 支持的 C 子集

`int`、单层 `int*`、一维 `int[N]`、`void` 返回函数；最多 8 参数；全局及局部变量、数组初始化、词法作用域、递归、if/else、while、for、break/continue、return。支持算术、位运算、比较、短路布尔、赋值及复合赋值、自增减、下标、解引用、取地址和 sizeof。

内置 `putchar`、`printint`、`printhex`、`exit`、`memcpy`、`memset`。整数为 32 位补码环绕，除法向零截断；除零和 `INT_MIN/-1` 按 RISC-V 语义处理。无预处理、字符串、char、结构体、类型转换、函数指针、switch、?: 或 do-while；不支持构造会明确报错。启用字节加载指令不会自动开放 char 类型。

## 测试与运行

```powershell
.\check.cmd
.\check.cmd --full
python -m tools.lint build/hello.elf --profile PF-01
python -m tools.check_isa_consistency isa/hw_caps.json --profile PF-01
```

Linux/WSL 使用 `bash check.sh`，完整验收为 `bash check.sh --full`。构建、lint、对照与 ISA 核对均有同名 `.sh` 入口。环境需安装 RISC-V GNU binutils/GCC 和 `qemu-riscv32`：

同时提供 `launch.ps1`、`check.ps1 [-Full]`；若本机 PowerShell 策略禁止脚本，直接使用 `.cmd` 入口，无需修改系统策略。

```bash
python3 -m tools.build bench/fib.c --qemu
qemu-riscv32 build/fib.elf
python3 -m tools.compare bench/fib.c
```

工作台 F6 调用相同的 QEMU 流程，30 秒超时，可终止。QEMU 使用独立 Linux 系统调用测试适配层；FPGA 运行时不包含 ecall。

本机验证：**88 项通过、1 项因缺少 QEMU 跳过**；已执行 9 profiles × 6 程序的实际汇编、链接和 lint。核心、关键模块、CLI、GUI 覆盖率门槛通过。**尚未执行 QEMU 运行矩阵、GCC 运行对照或上板验证**；`--full` 在缺少执行工具时直接失败。CI 配置包含 Linux 三环境完整验收，但尚未上传或运行 CI。

## 工作台与 CLI 对应

| 工作台动作 | CLI 对应 |
|---|---|
| 编译 / ISA 选择 | `python -m mycc file.c -o out.s --profile ... --enable ... --disable ...` |
| Token / AST / IR / Lowering | `--dump-tokens / --dump-ast / --dump-ir / --dump-lowering-report` |
| 导出汇编 / 诊断 | `-o out.s` / stderr 重定向 |
| 构建 FPGA / MMIO 设置 | `python -m tools.build ... --board-file ...` 或单项地址参数 |
| 运行 / lint | `python -m tools.build ... --qemu` + `qemu-riscv32` / `python -m tools.lint ...` |
| 环境检查 | `python -m mycc --doctor` |

GUI 与 CLI 共用编译入口及文本生成函数。编译失败保留上次成功汇编并标记，编辑源码或 ISA 后标记过期；诊断可双击跳转。GUI 设置位于 `~/.config/mycc/gui.json`。

代码目录：`mycc/core`（7 模块）、`mycc/cli.py`、`mycc/gui`（模型/视图分离）、`runtime`、`linker`、`tools`、`bench`、`tests`。原始需求和设计文档保留在 `需求分析&软件设计文档/`。
