> **Historical revision**: defaults and product scope are superseded by [SDD-MYCC-001 v1.3 编译器范围收敛修订.md](SDD-MYCC-001%20v1.3%20编译器范围收敛修订.md). Hardware protocol and previous evidence remain preserved.

# SDD-MYCC-001 v1.2 — CPU21 板卡适配修订

| 项目 | 内容 |
|---|---|
| 生效日期 | 2026-10-26 |
| 上一设计 | SDD-MYCC-001 v1.1；原文为历史设计 |
| 对应需求 | SRS-MYCC-001 v1.2 + v1.3 CPU21 修订 |
| 生效规则 | 本文覆盖冲突设计；未修改的模块、编号与接口约定继续沿用 |
| 变更编号 | CR-CPU21-001；软件版本 mycc 0.2.0 |

## DD-13：target 与 ISA profile 分离

`CompileOptions.target` 表示执行环境（`cpu21` / `generic`）；profile 仍只表示可用指令。CLI 默认 cpu21/cpu21，GUI 为 CPU21 工作台；纯 core API 为兼容原测试保留 generic 默认，调用方必须通过 options 明确选择板卡目标。`--qemu` 选择 generic 目标。

`core/isa.py` 中增加 CPU21 的 32 条编译能力集合及 `check_target(profile,target)`。编译驱动在源码解析前检查 target 能力，越界抛 `ProfileError(code=E-TARGET-ISA, exit_code=64)`。不把 unsigned divu/remu 当作 signed div/rem。原能力守卫 lowering 表保留。

目标相关分支仅用于存储布局、地址生成和启动 ABI；不以 profile 名、enable/disable 选项名决定指令选择。核心模块仍为原七个，无外部文件访问或 Qt 依赖。

## DD-14：哈佛数据初始化与地址生成

CPU21 模式下，所有全局对象分配到 `.bss`。代码生成器收集语义层已求值的非零初值，为用户主翻译单元生成 `__mycc_init_globals`，以立即数构造和普通 sw 写入。运行时库编译使用 `require_main=False`，不重复生成此入口；其全局状态使用零初值。`__mycc_` 前缀保留，用户声明被诊断拒绝。

全局地址通常用 lui/%hi + addi/%lo。无 lui 时，仅对 CPU21 4 KiB RAM 中的符号使用 `%lo(symbol)`，再 `slli 20; srli 20` 清除符号扩展，得到低 12 位绝对地址。启动中的 MMIO 地址来自已校验的低地址配置，直接构造；BSS 边界用重定位。不使用指令 ROM 中的常量池。

`linker/cpu21.ld`：ROM 32 KiB/RAM 4 KiB，均从 0 起；`.text.start` 为第一段；BSS ≤2048 字节；栈顶 4096，满足 ILP32 对齐。任何 `.data/.rodata` 均导致链接失败，防止误将 generic 汇编用于此目标。

## DD-15：生产启动、栈与中断安全

正式启动资产为 `runtime/cpu21-start.s`，流程如下：

1. 在 `_start` 执行硬件已有的 `csrrci zero,0x004,1`，关闭未接管中断。
2. 通过指令加载栈/BSS 边界，清 BSS；关闭鼠标中断源与显示光标。
3. 清零 600 个显存字，调用 `__mycc_init_globals`。
4. 调用 main，返回值传给 exit。
5. exit 同时写 LED/SEG 并自旋，无 ecall。

codegen 在函数帧分配和表达式 push 后、任何栈写入前，以 t3/t4 检查新 SP 不低于 `__bss_end+128`。因合法地址均为低正数，使用有符号 slt 同时检测大帧导致的负值下溢。失败跳转 `__mycc_stack_overflow`，无新增调用帧，构造状态 `0x5354414B` 后走 exit。128 字节覆盖现有算术/最小 ISA 辅助函数的内部暂存，保持正常调用的 ra/s0 不被检查代码破坏。

中断入口、ISR 寄存器保护、鼠标事件业务处理不在本次运行时接管范围。关闭中断是明确的板卡运行模式，不宣称已支持原扫雷中断应用。

## DD-16：现有 VGA 外设的运行时接口

`runtime/cpu21-console.c` 提供 putchar、字形映射与位置状态；printint/printhex 复用原 `runtime/io.c`。数字运算不受字体限制影响。

`vga_cell(index,glyph,color)` 由 CPU21 汇编提供：校验 `0<=index<1200`，地址为 `__vga_base+2*index`，分别 sb 写 6 位字形和 3 位颜色，保持邻格字节。`vga_cursor(col,row)` 检查 40×30 边界，写显示光标位置并启用光标。

字符输出为白色（颜色 7），支持换行、回车、制表和回绕；小写映射为大写，0/O、9/Q 共用已有字形，其余无对应字形者显示问号。GUI 对此明确提示。UART 不提供伪实现。

## DD-17：构建、ROM 与清单

`tools.build` 默认 CPU21，并在编译前校验硬件能力与 MMIO 配置。正式构建链为：

`C → CPU21 codegen → 正式启动/运行时 → GNU as(rv32im_zicsr) → CPU21 linker → lint → 固件`

`zicsr` 只用于汇编现有启动 CSR；白名单检查只对 `_start` 中的 csrrci 放行，其他 CSR 不自动加入 profile。generic/QEMU 保留各自启动与链接脚本；generic 标记或 ROM `.word/.byte` 数据不能作为 CPU21 输入汇编。

产物：`.elf/.bin`、32 位字 `.hex`（8192 字、NOP 补齐）、本地 `.vh`、32 位 Logisim 格式、另名 `.bytes.hex`，以及 `.manifest.json`（目标、profile 指纹、MMIO、字宽和二进制哈希）。生成器不回写 FPGA ROM 文件，也不执行 FPGA 工程的构建脚本。

## DD-18：GUI 与持久化

工作台默认 cpu21，显示 ROM/RAM、UART 不可用与字体限制；不支持的预设/组禁用。CPU21Board 六字段配置由 core 叶子类型验证，对齐、范围和显存重叠错误可恢复。

`build_request` 传入 CPU21 options。FPGA 构建使用当前成功的 CPU21 汇编；QEMU 运行将当前 C 内容另存到本软件 build 目录，重新按 generic 编译，避免混用全局初始化和启动 ABI。旧 GUI 配置不能表达新板卡时，提示并恢复 CPU21 默认值，不修改用户原始 C 文件。

## DD-19：原始 RTL 的只读正式固件验收

`tools.verify_cpu21` 使用外部原始 CPU RTL，在软件输出目录内编译 XSim；拒绝输出路径位于 FPGA 项目内。运行前后对外部项目逐文件 SHA-256；结果写入本软件 `build/cpu21-verification/results.json`。

测试平台为 `tests/rtl/cpu21_program_tb.v`：默认硬件 MIE=1，RAM/显存填脏值，注入外部 IRQ，使用板卡等效独立 ROM/RAM 与字节写；仅加载正式构建器的 `.hex`。结束时检查 LED/SEG 一致、返回状态和全部 600 个显存字；对光标、边界、屏幕回绕和栈故障另有场景。

不替换生产启动、不内嵌指令解释器、不将仿真器退出码 0 当作程序正确性。真实上板、完整 VGA 像素时序、ISR 与物理引脚仍需单独证据。

## 需求—设计—验证追溯

| 需求 | 设计落点 | 测试/证据 |
|---|---|---|
| FR-114、CN-02、FR-921 | DD-13、DD-18 | `test_hardware_capabilities_checked_before_source`、offscreen 组禁用 |
| FR-504、FR-517、FR-616 | DD-14 | `test_harvard_initializers_and_no_literal_pool`；cpu21_selftest 含无 lui/vshift |
| FR-602、CN-10、FR-605 | DD-15 | 正式启动 XSim、默认 MIE/IRQ 注入、LED/SEG |
| FR-617、FR-611 | DD-14、DD-15 | BSS 越界链接负例；cpu21_stack、cpu21_large_frame |
| FR-603、FR-921 | DD-16、DD-18 | hello/muldiv 字形比对、cpu21_vga、cpu21_wrap |
| FR-612、FR-618 | DD-17 | `test_word_rom_export`、manifest、正式 ROM 直接加载 |
| FR-619、AC-14、AC-15 | DD-19 | 输出路径负例、前后文件哈希、正式固件全显存比对 |

原设计 v1.1 的 DC-01..DC-06 和需求编号保留；此前 DC-07..DC-10 实现记录继续保留为历史，CR-CPU21-001 覆盖其中未适配板卡的实现选择。验证结果与尚未完成项以最新验收记录为准。
