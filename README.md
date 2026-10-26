# mycc 0.2.0 — CPU21 FPGA C 子集编译器

默认适配 `D:/Xilinx/Project/risc-v` 中的 CPU21：32 KiB 指令 ROM、4 KiB 独立数据 RAM、40×30 VGA。编译内核和 CLI 仅依赖 Python 3.11+ 标准库；GUI 使用 PySide6。

**正式构建器输出的固件已通过原始 CPU RTL 的 XSim 执行验证，包括返回状态和全部 600 个显存字比对。尚未进行物理下载、实际显示器或引脚验证。** 工具不会修改 FPGA 项目。

[工作台预览](docs/workbench.png) · [原始不兼容问题与历史失败证据](docs/FPGA_COMPATIBILITY.md) · [本次适配与验证记录](docs/CPU21_ADAPTATION.md)

## 启动与构建

当前目录已准备 `.venv`，可直接运行：

```powershell
.\launch.cmd
.\check.cmd

# 默认 CPU21 / cpu21 profile，生成汇编
python -m mycc bench/hello.c -o hello.s

# 生成完整 FPGA 固件
python -m tools.build bench/hello.c -o build/hello

# 对照实际板卡配置（与默认配置一致）
python -m tools.build bench/cpu21_selftest.c --board-file isa/cpu21.board.json -o build/selftest
```

全新环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt pytest coverage
```

纯 CLI 无需安装第三方包。构建固件需要 RISC-V GNU binutils；`python -m mycc --doctor` 检查环境。也提供 `launch.ps1`、`check.ps1` 与 Linux `.sh` 入口。PowerShell 禁止执行脚本时使用 `.cmd`，无需修改系统策略。

## CPU21 目标的实际行为

- 默认 `--target cpu21 --profile cpu21`，使用硬件支持的 32 条编译指令；乘法可走 mul，有符号除法/取余使用软件函数。启用 div/rem、auipc、字节加载等未实现能力会提前报错。
- 全局变量位于从 0 开始的独立 RAM。启动先清 BSS，再执行生成的全局初始化指令，支持带初值的全局标量和数组；不从指令 ROM 读取数据。
- 栈顶为 `0x1000`，16 字节对齐；BSS 超过 2 KiB 或 ROM 超过 32 KiB 拒绝链接。动态栈不足时，LED/七段输出 `0x5354414B`（STAK）后停止，避免静默破坏全局数据。
- 启动关闭尚未接管的中断及鼠标中断源。本版本不接管原扫雷应用的 ISR，不提供断点调试器。
- putchar/printint/printhex 输出到现有 VGA；CPU21 没有 UART。程序退出值同时写入 LED `0x1000` 与七段寄存器 `0x1004`，然后自旋。

### VGA 字形范围

VGA 由硬件字形表决定：每格 2 字节，低字节是 6 位字形，高字节是 3 位颜色。控制台输出为白色，小写显示为大写；**0/O、9/Q 共用已有字形**，减号使用横线，其他缺失字形显示问号。整数运算与返回值不受这个显示限制影响。

支持空格、换行、回车、4 列制表及 1200 格回绕；也可使用运行时函数：

```c
int main(void) {
    vga_cell(0, 16, 7);   /* 第 0 格，字形 A，颜色 7 */
    vga_cursor(1, 0);     /* 列、行；启用硬件光标 */
    return 0;
}
```

### 地址配置

工作台可配置 LED、七段数码管、VGA、显示控制/光标和鼠标中断控制地址；不再把不存在的 UART 或专用退出寄存器作为板卡配置。

```powershell
python -m tools.build bench/hello.c --board-file isa/cpu21.board.json
python -m tools.build bench/hello.c --led 0x1000 --seg 0x1004 --vga-base 0x2000
```

地址必须与实际硬件一致。配置仅改变软件访问位置，不会增加硬件外设或改变 VGA 协议。校验包括 4 字节对齐、低地址范围和显存重叠。

## 产物与 ROM 集成

`python -m tools.build ... -o build/hello` 输出：

| 文件 | 用途 |
|---|---|
| `hello.elf` / `.bin` | 链接结果 / 原始小端二进制 |
| `hello.hex` | **8192 行、每行一个 32 位字**，直接供 `reg [31:0] rom[]` 的 `$readmemh` 加载；NOP 补齐 |
| `hello.vh` | `rom[i] = 32'h...;` 初始化语句，供手工审核后集成 |
| `hello.logisim.hex` | Logisim v2 raw 的 32 位字格式 |
| `hello.bytes.hex` | 单独保留的字节格式，不能与 32 位 ROM 格式混用 |
| `hello.manifest.json` | target、profile 指纹、MMIO、字宽与二进制 SHA-256 |

所有产物保存在本软件输出目录。工具不自动复制 `.vh/.hex` 到 `risc-v`，也不调用会回写硬件工程的构建脚本。生成 ROM 镜像不等于已生成 bitstream 或已下载开发板。

## 验证

```powershell
# 单元、真实汇编/链接、54 组合 generic profile 矩阵、GUI offscreen、覆盖率
.\check.cmd

# 再用本机 Vivado 和原始 CPU21 RTL 检查正式固件
.\check.cmd --cpu21 --fpga-root D:\Xilinx\Project\risc-v

# 单独执行板卡仿真
python -m tools.verify_cpu21 --root D:\Xilinx\Project\risc-v

# 检查生成固件的指令
python -m tools.lint build/hello.elf --target cpu21 --profile cpu21
```

CPU21 验证使用正式启动代码，不替换成测试启动。RAM/显存先填脏数据，运行中注入未接管 IRQ，检查退出值、全显存字形/颜色、光标、屏幕回绕、全局初值、字节 memcpy/memset、除法边界和栈故障。前后逐文件哈希保证 FPGA 项目不变；验证输出目录若位于 FPGA 项目中会被拒绝。

最新结果与限制见 [适配记录](docs/CPU21_ADAPTATION.md)。QEMU/GCC 对照是另一条路径，本机缺少 `qemu-riscv32`；不影响已完成的 CPU21 RTL 执行证据，也不能据此声称 QEMU 对照通过。`check --full` 仍要求 QEMU/GCC。

## 通用目标与 ISA 观察

原有 RV32 profile 保留，超出 CPU21 硬件的能力需要显式选择通用目标：

```powershell
python -m mycc bench/muldiv.c --target generic --profile PF-05 -o build/generic.s
python -m mycc bench/muldiv.c --dump-lowering-report -o build/cpu21.s
python -m mycc --dump-isa
python -m mycc --dump-isa-whitelist --profile PF-01
python -m mycc bench/arrays.c --disable lui,vshift -o build/fallback.s
```

`--enable/--disable` 支持指令或组、逗号列表、重复参数；disable 优先。支持 tokens/AST/IR/lowering dump 和 stats。PF-01..PF-07 的实际指令数依次为 26、25、23、32、29、30、39；原文计数修正保留在历史实现记录中。

Linux/WSL 的 QEMU 流程：

```bash
python3 -m tools.build bench/fib.c --qemu
qemu-riscv32 build/fib.elf
python3 -m tools.compare bench/fib.c
```

工作台 F6 使用相同流程，从当前 C 源码重新按 generic 编译；FPGA 构建和 lint 使用 CPU21 目标。`isa/board.example.json` 是旧 generic UART 示例，只有 `--target generic` 才适用；实际 CPU21 配置为 `isa/cpu21.board.json`，ISA 参考为 `isa/cpu21.json`。

## 语言与文档

支持 int、单层 int*、一维数组、最多 8 参数、函数递归、全局/局部变量、if/else、while/for、break/continue、return、算术/位运算/比较/短路、自增减、赋值、下标、取地址/解引用和 sizeof。没有预处理、字符串、char、结构体、类型转换、函数指针、switch、?: 或 do-while；不支持构造会明确报错。

需求和设计采用留痕修订：原 SRS v1.2 / SDD v1.1 正文保留；新增 **SRS v1.3 / SDD v1.2 CPU21 修订**，通过 CR-CPU21-001 记录原因、原/新条款、实现与测试追溯，冲突项以修订为准。

目录：`mycc/core`（七模块）、`mycc/gui`、`runtime`、`linker`、`tools`、`bench`、`tests`、`需求分析&软件设计文档`。
