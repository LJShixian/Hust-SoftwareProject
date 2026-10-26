> **Historical revision**: defaults and product scope are superseded by [SRS-MYCC-001 v1.4 编译器范围收敛修订.md](SRS-MYCC-001%20v1.4%20编译器范围收敛修订.md). Hardware protocol and previous evidence remain preserved.

# SRS-MYCC-001 v1.3 — CPU21 板卡适配修订

| 项目 | 内容 |
|---|---|
| 生效日期 | 2026-10-26 |
| 上一基线 | SRS-MYCC-001 v1.2，原文保留为历史基线 |
| 新基线组成 | v1.2 全文 + 本修订；冲突项以本修订为准，未列条款继续有效 |
| 变更授权 | 用户要求软件适配实际 FPGA，必要时修订需求/设计并留痕；不得修改 `risc-v` 项目 |
| 关联设计 | SDD-MYCC-001 v1.2 CPU21 板卡适配修订 |
| 实现版本 | mycc 0.2.0 |

## CR-CPU21-001 变更原因与事实来源

对实际 `D:/Xilinx/Project/risc-v` 项目的 RTL、板级顶层及扫雷链接脚本进行只读核验后，发现 v1.2 的若干目标假设与硬件不符。原始核验和失败案例保存在 `docs/FPGA_COMPATIBILITY.md`，不是删除失败证据后重新宣称通过。

硬件事实：32 KiB 指令 ROM 与从零开始的 4 KiB 数据 RAM 相互独立；支持 lui、寄存器移位、xor、完整条件分支、mul；没有有符号 div/rem、auipc 和字节/半字加载。MMIO 没有 UART；VGA 为 40×30、2 字节字形/颜色单元，字形表有表示范围限制。

## 需求修订表（保留原需求 ID）

| 原编号 | 原要求/假设 | v1.3 的生效要求 | 验证依据 |
|---|---|---|---|
| AS-02 / AS-03 | lui/变量移位待补；数据内存为 16 KiB | CPU21 已实现这些指令；ROM 32 KiB，RAM 为 `0x0000..0x0FFF` 的 4 KiB。通用目标保留旧布局作为独立目标 | RTL 参数、RAM 地址选择；正式固件 XSim |
| AS-07 / FR-603 | putchar 同时写串口与 VGA | CPU21 的 putchar 仅写现有 VGA；UART 在 CLI/GUI 中明确不可用，不把 LED 当作串口。通用目标可保留原 UART 协议 | 字形及颜色全显存比对 |
| FR-111 / CN-02 | 默认 PF-01，26 指令 | CLI 和 GUI 默认 `target=cpu21, profile=cpu21`，为实际硬件可供编译器使用的 32 指令子集；PF-01..PF-07 保留，通用目标 `--target generic` 默认 PF-01 | 默认参数测试、ISA 越界负例 |
| FR-114 / CN-16 | profile 校验 | CPU21 在解析源码前校验 profile 是实际编译能力集合的子集；禁止 div/rem/auipc/lb/lbu/lh/lhu 等未实现能力；不静默忽略 enable 请求 | `E-TARGET-ISA`、退出码 64 |
| CN-07 / FR-503 / FR-611 | 固定链接布局，对齐目标映射 | CPU21 ROM 和 RAM 都从 0 起、属于独立空间；栈初值 `0x1000`，16 字节对齐。含运行时的 BSS 不超过 2 KiB，至少留出 2 KiB 栈空间；ROM 超过 32 KiB 拒绝链接 | 链接断言及越界测试 |
| FR-504 | 有初值的全局数据放 `.data` | CPU21 全局变量均分配 BSS；清零后调用编译器生成的 `__mycc_init_globals`，以指令写入非零初值。禁止依赖 ROM 数据加载或外部 RAM 加载器。generic 保留 `.data` 语义 | 全局标量/数组初值执行测试；正式 ELF 无 `.data` |
| FR-517 | 无 lui 的常量/地址回退 | CPU21 常量采用指令合成；全局 RAM 地址使用 `%lo` 重定位后零扩展低 12 位，禁止代码字面量池。启动 MMIO 地址按低地址配置合成 | 禁用 lui 的独立全局变量与综合自测 |
| FR-601 / FR-602 | `_start` 初始化栈、BSS 后调用 main | CPU21 `_start` 使用立即数重定位，关闭未接管中断、关闭鼠标中断源、清 BSS/显存、执行全局初值、调用 main；不能通过 lw 读取指令 ROM 中的 `.word` | 默认 MIE=1 且注入 IRQ 的 XSim；初始 RAM/显存填脏数据 |
| CN-10 | 运行时不生成 CSR 指令 | 对 CPU21 `_start` 允许一条 `csrrci zero,0x004,1`，只用于启动时关闭未接管中断。其他编译输出仍禁止 CSR；退出不使用 ecall | lint 在 `_start` 范围内的窄例外 |
| FR-605 | 专用 MMIO 输出状态后自旋 | CPU21 把退出状态同时写 LED `0x1000` 与七段寄存器 `0x1004` 后自旋。它们是现有显示外设，不宣称存在专用退出寄存器 | 两个实际 MMIO 输出一致性 |
| FR-608 / FR-612 | 输出 `.hex` / `.bin` | CPU21 `.hex` 为 8192 个小端组装的 32 位字，NOP 补齐；`.vh` 为本地 `rom[i]` 赋值；Logisim 文件为 32 位字。字节形式另存 `.bytes.hex`，不能混用 | 字序/容量/首指令测试及 RTL 直接加载 |
| FR-905 / FR-915 | ISA 与设置面板 | 默认 CPU21，禁用硬件不支持的组及预设；旧 UART/退出配置迁移为明确提示后恢复 CPU21 默认值；保存基线与差集及 CPU21 MMIO 配置 | offscreen 设置往返与旧配置回退 |
| FR-917 | GUI 功能均有 CLI 等价物 | FPGA 构建使用 `tools.build --target cpu21`；QEMU 运行从 C 源码重新按 generic 编译，不复用 CPU21 汇编；增加只读 CPU21 RTL 验收命令 | 命令构造与集成测试 |

### 字形表示的明确限制

CPU21 运行时显示小写为大写，`0` 使用字母 O 字形、`9` 使用 Q 字形，减号用横线；不支持的可打印字符显示已有问号字形。空格、换行、回车、4 列制表及 1200 格回绕均有确定行为。此规则在 GUI 和 README 展示，不能声称输出完整 ASCII 字体。限制只影响显示，不改变整数运算结果或程序返回值。

### 新增需求

| ID | 优先级 | 要求 | 自动验证 |
|---|---|---|---|
| FR-616 | P0 | CPU21 全局初值通过启动指令写入，保持不同变量地址独立 | `cpu21_selftest`，含禁用 lui/vshift |
| FR-617 | P0 | 函数帧及表达式临时栈在写入前检查 BSS 边界，保留 128 字节运行时余量；不足或下溢时输出 `0x5354414B`（STAK）并自旋 | 无限递归、超大局部数组 XSim |
| FR-618 | P0 | 输出 ROM 字序/位宽明确，附构建清单记录 target、profile 指纹、MMIO 和二进制 SHA-256 | ROM 单元测试、manifest 检查 |
| FR-619 | P0 | 构建/验证产物仅写本软件输出目录；RTL 验证不得执行硬件工程回写脚本，且拒绝将验证输出放入 FPGA 项目 | 输出路径负例、前后源文件哈希 |
| FR-921 | P1 | GUI 展示真实板卡容量、UART 不可用与字形限制，不提供无效硬件能力开关 | offscreen 控件状态测试 |
| FR-922 | P1 | CPU21 MMIO 配置包含 led、seg、vga_base、display_ctrl、display_cursor、mouse_ctrl；校验对齐、地址范围及重叠 | 配置故障测试 |
| AC-14 | P0 | 正式构建器生成的 CPU21 固件，无测试启动替换，必须在原始 RTL 的板卡等效 ROM/RAM/MMIO 模型上通过程序结果及全部 600 显存字比对 | `python -m tools.verify_cpu21` |
| AC-15 | P0 | 验证前后 FPGA 源文件哈希一致；真实上板与仿真证据明确区分 | 验证 JSON；无上板证据时明确标注 |

## 保持有效的约束与未完成的验收

核心/CLI 标准库依赖、GUI 仅 PySide6、七模块边界、GUI/CLI 共用编译器、诊断结构、确定性、跨 ISA 语言一致性、覆盖率门槛均保留。未新增 char、字符串、结构体、调试器或内嵌模拟器；vga_cell/vga_cursor 是外部运行时函数接口。

原有性能、资源、三环境、GCC 对照等条款不因本修订自动宣称通过，也不静默删除。新增 `check --cpu21` 为本机 CPU21 正式固件验收路径；`--full` 仍要求原有 QEMU/GCC 路径。物理上板结果须另行取得。

## 变更控制留痕

提出 → 只读硬件核验 → 六项失败/不匹配记录 → 用户授权软件侧适配 → 本修订与 SDD 同步 → 单元/覆盖率与正式 RTL 验收 → Git 提交保存。原 v1.2 文档仅增加被后续修订的导航标记，正文保留供对比。
