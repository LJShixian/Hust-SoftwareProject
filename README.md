# mycc — 可配置指令集的 C 子集编译器（v3.1）

> **当前集成分支为 `main`**：`main` 的第一版是 `8a5d050`；`zjb` 在其上完成前四轮（对齐需求/设计、接入 Logisim 课堂 CPU、标准 RISC-V 系统调用、字符串字面量与 `printf`/`scanf`），`v3.1-ide` 追加第五轮 **v3.0**（走查修复与镜像体积优化）和第六轮 **v3.1**（IDE 化工作台、主题、格式化/补全、Ctrl+S、完整 CLI 开关映射与输出路径修复），第七轮 **v3.1 演示与 GUI 修复**（行号跟随滚动、滚轮防误改、自定义指令可回退、课堂演示脚本）已合入 `main`。改动与验证数据见 [本分支改动说明](#本分支改动说明)。

mycc 3.1.0 接收 **一个受限 C 源文件和可用指令集合（ISA）**，生成 **GNU RISC-V 汇编、源码诊断和指令选择说明**。可在命令行使用，也可在 PySide6 工作台中编辑、编译和查看结果。

当前产品边界见 [范围说明](docs/guides/scope.md)。常用入口是 `python -m mycc`；CPU21 固件构建是可选集成，需要显式选择。原 FPGA 扫雷项目继续由原有 GCC 流程构建。

导航：[版本与分支](#版本与分支) · [本分支改动说明](#本分支改动说明) · [快速使用](#快速使用) · [目录结构](#目录结构) · [运行流程](#运行流程) · [实现方式](#实现方式) · [ISA 与语言范围](#isa-与语言范围) · [外部运行与验证](#外部运行与验证) · [文档索引](docs/README.md)

## 版本与分支

当前源码版本为 **3.1.0**，集成分支为 **`main`**（已合入 `v3.1-ide`），`v3.1-ide` 的基线是 `zjb`（远端 `origin/zjb`）。版本关系如下，后一版只在前一版上增加功能或修正，不回退已有行为：

| 阶段 | 所在分支 | 主要工作 |
|---|---|---|
| 前四轮（v2.0） | `zjb` | 需求/设计对齐、Logisim 课堂 CPU 适配、标准系统调用、字符串与 `printf`/`scanf` |
| 第五轮（v3.0） | `v3.1-ide` | 按代码走查修复、Logisim 镜像/ISA 预检、体积与转换时间优化 |
| 第六轮（v3.1） | `v3.1-ide` | IDE 式 GUI、主题、全部 CLI 开关、格式化/自动缩进/补全、Ctrl+S、输出文件/目录 |
| 第七轮（v3.1 演示与 GUI 修复） | `main` | 行号跟随滚动、滚轮防误改、自定义指令可回退、课堂演示脚本 `demo.cmd` |

因此，README 中 v3.0/v3.1 的说明是**累计关系**：v3.1 包含 v3.0 的全部修复和优化，而不是两套互相替代的配置。

## 本分支改动说明

`main` 的 `8a5d050` 是第一版实现。`zjb` 在其上完成前四轮；`v3.1-ide` 追加 v3.0 与 v3.1，`main` 再合入第七轮，下面按七轮累计列出（`git diff --stat 8a5d050` 可看净变化）：

### 轮次一：对齐需求与设计文档

| 主题           | 位置                                        | 内容                                                                                                                                                          |
| -------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 指令选择可追溯 | `mycc/core/codegen.py`、`driver.py`     | `LoweringRecord`：每条降级记录源位置 `file:line:col`、选中理由、被拒方案（含缺失指令）、指令数增量；`--dump-lowering-report` 增加位置与 `Δ指令` 两列 |
| 诊断质量       | `mycc/core/parser.py`                     | 文件作用域出现语句时报 `E-PARSE-FILE-SCOPE` 并给出修复建议                                                                                                  |
| 诊断质量       | `mycc/core/sema.py`                       | 新增 `W-SEMA-INFINITE-RECURSION`，只警告不阻断生成                                                                                                          |
| RARS 后端      | `mycc/rars.py`、`mycc/cli.py`           | `--rars` 输出 RARS 可直接汇编运行的单文件 `.asm`                                                                                                          |
| 文档一致性门禁 | `tools/check_docs.py`、`tools/check.py` | README 预设表、`configs/isa/presets` 与 `core/isa.py` 三方对齐；另生成源码哈希                                                                            |
| 工作台         | `mycc/gui/views.py`、`workbench.py`     | 去掉与菜单重复的工具栏；导出按当前页决定格式；悬停即在状态栏解释；修正能力配置被持久化成错误指令数的问题                                                      |
| 回归工具健壮性 | `tools/verify_cpu21.py`                   | 源码哈希按 UTF-8 读取；新增 ASCII 暂存目录，绕开 Vivado `-testplusarg` 无法承载非 ASCII 路径的限制                                                          |

### 轮次二：硬件综合训练 Logisim 课堂 CPU

目标：**现场写一段 C，一条命令拿到可载入 Logisim ROM/RAM 的镜像**，不依赖 Java、RARS 或 GNU 工具链。

| 主题         | 位置                                                                            | 内容                                                                                                                                                                                                           |
| ------------ | ------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 新目标与预设 | `adapters/logisim/`、`mycc/core/isa.py`、`configs/isa/presets/PF-08.json` | `--target logisim` 与预设 `PF-08`：按课程设计报告表 1.1 建模 24 条可编码指令（硬件译码 31 条），1024 字 ROM / 1024 字节 RAM，无链接器                                                                      |
| 内置汇编器   | `mycc/encode.py`（新增）                                                      | 把自产的单文件汇编直接编码成机器码：R/I/S/B/U/J 型、`%hi/%lo`、`.text/.data/.align/.word/.space`；与真 RARS 逐字比对通过                                                                                   |
| 镜像导出     | `mycc/cli.py`、`mycc/rars.py`                                               | `--logisim` 输出 `v2.0 raw` 的 `.rom.hex` 与（有初值全局变量时）`.ram.hex`；入口存根装载 `sp`（默认 1024），全局变量改用有界 `%lo` 重定位（Harvard 上 `lw` 读不到 ROM）                          |
| 缺陷修复     | `mycc/rars.py`、`tools/build.py`                                            | ① `--rars` 原先不对 `runtime.s` 做降级，受限指令集下会漏出 `sltu`；② `switch` 的 `.word` 跳转表落在 `.text` 里，RARS 直接拒绝、硬件也读不到；③ `.logisim.hex` 原先逐字节写出，字宽 ROM 会跑飞 |
| 预检工具     | `tools/check_logisim.py`（新增）                                              | 零依赖：把镜像反汇编回来检查指令是否都在该 CPU 的译码范围内、容量是否超限                                                                                                                                      |
| 交叉校验     | `tools/check_rars.py`（新增）                                                 | 与真 RARS 逐字对照汇编结果，并对同一程序做行为差分；缺 Java 时自动跳过                                                                                                                                         |
| 课堂演示     | `examples/logisim/demo.c`、`demo_pause.c`（新增）                           | 全局数组初值 → 指针遍历累加 → 最大值 → 软件乘 → 软件除 → SLL → XOR，七行可读文本；`demo_pause.c` 是每行后面停一次钟的讲演版                                                                            |

### 轮次三：I/O 改成标准 RISC-V 系统调用

轮次二把 `ecall` 当成私有协议（`a7=34` 显示十六进制、其它值停机），课堂上演示只能看数码管、
键盘也无法输入。本轮把 I/O 改成**标准 RISC-V 系统调用约定**，与 RARS 完全一致：

| 主题         | 位置                                           | 内容                                                                                                                                                                        |
| ------------ | ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 系统调用约定 | `mycc/rars.py`                               | `a7` 选服务号、参数与返回值在 `a0`：`10`=退出、`11`=打印一个字符、`12`=读一个字符。`putchar`/`getchar`/`exit` 三个存根就三行 `addi a7,zero,N` + `ecall` |
| 分层修正     | `runtime/io.c`、`mycc/rars.py`             | `printint`/`printhex` 不再是"系统调用变形"，它们是用 `putchar` 写的普通 C 函数，随镜像内联；硬件只需认"打一个字符"                                                    |
| 符号驱动链接 | `mycc/rars.py`                               | 多个翻译单元合并时统一给局部标号加前缀（`_relabel`），并按引用关系做段级 GC（`_drop_unreferenced`），镜像只留下真正用到的运行时函数                                     |
| 门禁         | `tests/test_logisim.py`                      | 断言 `a7=11/12` 的存根、`printint`/`printhex` 是真函数而非 shim、合并后标号唯一、GC 不删跨块跳转目标                                                                  |
| 硬件指南     | `adapters/logisim/HARDWARE-REUSE.md`（新增） | 复用现有的 `ecall` 输出电路：改常量 `0x22`→`0x0a` 并拆反相器（停机条件）→ TTY 接 Write Enable（输出）→ 键盘 + 三个选择器（输入），附引脚表与排查表                 |

### 轮次四：字符串字面量与 `printf` / `scanf`

前三轮里写文本只能用 `int` 数组加字符字面量，输出只能 `printint`/`printhex`。本轮补上
真实 C 代码需要的表达力，**不动硬件、不引入变参 ABI**：

| 主题         | 位置                                                               | 内容                                                                                                                                                                                                                                         |
| ------------ | ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 字符串字面量 | `mycc/core/lexer.py`、`parser.py`、`sema.py`、`codegen.py` | `"abc"` 解码成 `int` 数组落进 `.data`（Harvard 上 `lw` 只到 RAM），类型为 `int*`；相同字面量共用一个标号；非法转义、未闭合、非 ASCII 分别报错                                                                                      |
| 格式串降级   | `mycc/core/sema.py`、`codegen.py`                              | `printf`/`scanf` 在**编译期**解析：`%d`→`printint`、`%x`→`printhex`、`%c`→`putchar`、`%s`→`printstr`、`scanf` 的 `%d`→`readint`、`%c`→`readchar`。参数个数与类型全部编译期校验，格式串必须是字面量 |
| 运行时助手   | `runtime/io.c`、`runtime/input.c`（新增）                      | `printstr`、`readint`、`readchar` 用 C 写在 `putchar`/`getchar` 之上。输入助手单独成文件，因为板卡 / QEMU / CPU21 端口没有键盘                                                                                                     |
| 门禁         | `tests/test_formatting.py`（新增）                               | 字面量入数据段与去重、每个转换对应一个助手调用、8 种格式错误诊断、真实 RISC-V 上的端到端输出比对                                                                                                                                             |
| 演示程序     | `examples/logisim/knapsack.c`（新增）                            | 0/1 背包（洛谷 P1048 同型）：`scanf` 读入、二重循环逆序递推、`imax` 函数调用、`printf` 输出。ROM 964 字 / RAM 660 字节（v3.0 优化后为 956 / 644）                                                                                                                 |

### 轮次五（v3.0）：走查修复与体积优化（2026-11-01）

v3.0 是 v2.0 的质量迭代：按第二轮代码走查逐条修复，并压缩 Logisim 镜像与转换时间。对外行为有 5 处**有意收紧**（见下方"行为收紧"），没有删除已有功能。

#### 修复

| 问题 | 修复 | 位置 |
|---|---|---|
| `sizeof(数组)` 作为数组长度被提前折叠成 4 | 数组边界移到 sema 的 `resolve_array()`，按真实类型求值 | `mycc/core/parser.py`、`sema.py` |
| `--rars --no-lui` 的全局/字符串地址错（读到错误变量） | 检测 `.Lpc_` 地址池并明确拒绝（64），不再把 `.word` 搬走却留下 `lw 8(rd)` | `mycc/rars.py`、`cli.py` |
| 精简 ISA 下 `__mv_*` 助手重复/丢失 | 各单元编译后剥离助手，合并后只 `lower_assembly` 一次；已有助手时不重复追加 | `mycc/rars.py`、`codegen.py` |
| `--logisim` 可写出含 `lui` 的非课堂镜像；超 1024 字也照写 | 新增 `validate_image()`（ISA + 1024 字 ROM + 1024 字节 RAM）；`--logisim` 必须配 `--target logisim` | `mycc/encode.py`、`cli.py`、`rars.py` |
| `scanf` 把格式串里的普通文本打印到 stdout | `scanf` 不再生成 text 计划；普通字面量报 `E-SEMA-FORMAT`，只允许空白分隔 | `mycc/core/sema.py`、`codegen.py` |
| 非法 `--stack-top` 触发 ICE（退出码 2） | 捕获 `ValueError`，返回 64 | `mycc/cli.py` |
| `images()` 默认不装 `sp`，硬件首压栈写 `0xFFFFFFF0` | `logisim` profile 默认 `stack_top=1024` | `mycc/rars.py` |
| `int *p[2]` 被静默当成 `int[2]` | 声明符已有 `*` 时遇到 `[` 报 `E-UNSUPPORTED-CONSTRUCT` | `mycc/core/parser.py` |
| 递归 `main` 调用落到入口存根 | 重命名 `main` 后，同时把 `jal ...,main` 改成 `__mycc_main` | `mycc/rars.py` |
| `tools/check.py` 的 logisim 成功提示不可达；未接入 RARS 对照 | 修正缩进，logisim 之后调用 `check_rars`（无 jar 自动跳过） | `tools/check.py`、`check_rars.py` |
| `_io_unit` 编译失败时对 `Diagnostic` 做 `''.join` | 改用 `format_diagnostic` | `mycc/rars.py` |
| GUI 单条指令设置触发 `normalize_capabilities` KeyError | `GROUPS.get(name,{name})`；设置文件改为原子写 | `mycc/gui/workbench.py` |
| GUI 版本/标题硬编码；新建/保存后标题不更新 | 使用 `__version__`/`PySide6.__version__`；新建/保存后更新标题 | `mycc/gui/views.py` |
| Ctrl+加号无法放大（美式键盘上 `Ctrl++` 实际是 Ctrl+Shift+'='） | 应用级事件过滤器按物理键处理 `Ctrl+'+'`/`'-'`，菜单同时注册 `Ctrl++`、`Ctrl+=`、`Ctrl+Shift+=` | `mycc/gui/views.py` |
| RARS jar 测试写死 `D:\Desktop\...`；一个测试用了不支持的 `?:` | 改用 `MYCC_RARS_JAR` 或 `tools/rars.jar`；测试源改为 `if`；精简 profile 测试补 `assemble` | `tests/` |
| 版本此前仍为 0.3.0；示例注释/统计过时 | 统一为 **3.0.0**；更新 README、demo 注释、RARS 工具说明 | 全文 |

#### 优化

| 优化 | 效果 |
|---|---|
| `_io_unit` 按 profile 缓存 | `check_logisim` 的 11 个示例只编译一次 `io.c`/`input.c`（22 次 → 2 次） |
| `printhex` 用 `i << 2` 代替 `i * 4` | 只打印十六进制的程序不再需要 `__mulsi3`；`hello.c` ROM 462 → 450 字 |
| `.Lsigned_div` 移入 `__divsi3` 段 | 只用 `/`/`%` 的程序不再被迫带 `__mulsi3` |
| `lower_assembly` 保存 10 个寄存器（原 16 个）、48 字节栈帧（原 64） | 每条降级指令少 12 条保存/恢复指令；精简 profile 的 ROM 与时间下降 |
| `_drop_unreferenced` 用一次 `Counter` 计数 | 从 O(块数 × 全文) 降为线性；小 ROM 的 GC 更快 |
| CLI 镜像预检 | 超容量/越界在写出前失败，不再生成跑飞的 ROM |
| 设置文件临时文件 + `replace` | 断电/磁盘满不留下半个 `gui.json` |
| `check.py` 接入 RARS | 编码逐字对照与行为差分纳入常规检查（有 jar 时） |

Logisim 镜像体积（修改前 → 修改后，字）：`hello 462→450`、`shifts 319→272`、`knapsack 964→956`、`arrays 473→463`、`control 411→401`、`fib 350→340`、`pointers 414→404`；`demo` 保持 771。背包 RAM 660 → 644 字节。11 个示例预检 0 问题（ROM 272~956 / 上限 1024）。

#### 行为收紧

| 场景 | v2.0 | v3.0 |
|---|---|---|
| `--rars` + 无 `lui` + 全局/字符串 | 生成地址错误的 listing | 明确报错 64；改用 `--target logisim` 或保留 `lui` |
| `scanf` 格式串含普通文本（如 `"X%d"`） | 把 `X` 打印到 stdout | `E-SEMA-FORMAT`；只支持 `%d/%c` 与空白 |
| `int *p[2]` | 静默按 `int[2]` 编译 | `E-UNSUPPORTED-CONSTRUCT` |
| `--logisim` 未指定 `--target logisim` | 写出含 `lui` 的镜像 | 返回 64 并提示加 `--target logisim` |
| `--stack-top` 超出 32 位 | ICE（2） | 用法错误（64） |
| Logisim ROM/RAM 超限 | 静默写出 | 64，提示具体超限 |

#### v3.0 验证（2026-11-01）

| 项目 | 结果 |
|---|---|
| `python -m compileall -q mycc adapters tools runtime` | 退出码 0 |
| `python -m pytest -q` | **172 passed, 13 skipped**（skip 为 RARS/CPU21/外部工具链缺失） |
| `python -m tools.check_logisim` | 13 个程序，0 问题（ROM 272~956；RAM ≤ 644 字节） |
| `python -m tools.check_docs` / `check_architecture` | 通过 |
| `python -m mycc --version` | `mycc 3.0.0` |
| RV32I 解释器运行 | `demo` 七行输出正确；`printf` → `hello 42 0x000000ff A ok`；`scanf` 输入 `17 25` → `17+25=42`；控制流/指针/`sizeof`/`INT_MIN` → `8/20/12/-2147483648` |
| GUI 缩放快捷键 | QTest 验证 `Ctrl+Shift+'='`、`Ctrl+'='`、`Ctrl+'-'` 均改变编辑器字号 |
| CLI 错误路径 | 无 lui 的 RARS、缺 target 的 `--logisim`、非法 `--stack-top`、2422 字 ROM 均返回 64 |

限制：本机没有 RARS jar，`tools.check_rars` 与 `test_formatting` 的 RARS 端到端用例按设计跳过；CPU21/Vivado 回归未在本环境执行。`pytest` 在受限沙箱中需把 basetemp 指到工作区（pytest 自建 0o700 临时目录会被沙箱 ACL 拒绝），这是环境限制，项目代码未依赖该修补。



### 轮次六（v3.1）：IDE 化工作台（2026-11-01）

v3.1 把工作台从“能编译的窗口”升级为可日常使用的 IDE 式界面，并把 CLI 的每个开关映射到 GUI。

#### 外观与交互

- 顶部工具栏：新建 / 打开 / 保存、主编译按钮、停止、命令预览、环境自检、主题下拉。
- 左侧可滚动设置栏，按“构建与输出 / 指令集 / 输出与外观 / 快捷操作”分组；编辑器占据主区域，底部是诊断表与输出页。
- 编辑器带文件头、行号、当前行高亮、行列位置、语法高亮；状态栏显示目标、profile、主题、版本。
- 编辑器智能：回车按当前括号层级自动缩进，`(`/`[`/`{` 自动配对，输入 `}` 自动回退缩进，Tab/Shift+Tab 整行缩进；`Ctrl+Shift+F` 整理当前文件。
- 补全：`Ctrl+Space` 手动唤起；输入两个及以上标识符字符时自动弹出；候选包含当前文件已出现的变量、函数、参数、关键字和 `printf`/`scanf`/`putchar` 等助手。
- 四种外观：**跟随系统、浅色、深色、高对比度**；工具栏、菜单、侧栏都可切换，设置写入 `~/.config/mycc/gui.json`。
- 视图菜单可隐藏/显示侧栏与底部面板；支持 F5 编译、Ctrl+S 保存、Ctrl+Shift+P 命令预览、Ctrl+Shift+I ISA 详情、Ctrl+Shift+D 环境自检、Ctrl+Shift+K CLI 开关对照、Ctrl+Shift+E 导出。
- 设置侧栏实时显示 ISA 指令数；支持“自定义单条指令…”对话框，逐条勾选所有后端指令。

#### 全部 CLI 开关的 GUI 对应

| CLI 开关 | GUI 位置 |
|---|---|
| `source.c` | 文件 → 打开 / 编辑器 |
| `-o PATH` | 构建与输出 → 输出路径（文件或文件夹）+ “编译成功后写入” |
| `--target generic/cpu21/logisim` | 构建与输出 → 目标（切换目标会自动切 profile 和输出格式） |
| `--rars` / `--logisim` | 构建与输出 → RARS 单文件 / Logisim 镜像 |
| `--stack-top N` | 构建与输出 → 栈顶 |
| `--profile P` | 指令集 → Profile |
| `--isa-file JSON` | 指令集 → ISA 文件 |
| `--enable` / `--disable` | 指令集 → 组复选框；更细粒度用“自定义单条指令…” |
| `--no-lui` / `--no-vshift` | 指令集 → 兼容开关（与取消 `lui`/`vshift` 等价） |
| `--dump-tokens/ast/ir/lowering-report` | 输出与外观 → 显示对应输出页 |
| `--dump-isa` / `--dump-isa-whitelist` | 输出与外观 → 命令包含；ISA 详情查看清单/白名单 |
| `--stats` | 输出与外观 → 显示各阶段耗时 |
| `--doctor` | 构建 → 环境自检… |
| `--version` / `--help` / `--gui` | 帮助 → 关于 / 帮助 → CLI 开关对照 / 当前窗口 |

“命令预览”会按当前设置生成等价的 `python -m mycc …` 命令并支持一键复制，方便在终端复现；目标为 Logisim 时自动带上 `--stack-top`/`--target logisim`，RARS 时带上 `--rars`，`--no-lui`/`--no-vshift` 也会显示为别名而不是冗长的 `--disable`。

#### 输出与验证

- 勾选“编译成功后写入”后，通用目标写 `.s`，RARS 写单文件 `.s`，Logisim 写 `.asm` + `.rom.hex`（有初始化数据时再加 `.ram.hex`）。
- 输出路径可以是文件，也可以是文件夹：文件夹用“文件夹…”选择（或直接输入现有目录/带 `/` 的目录/无后缀路径），按源文件名写入 `demo.s`、`demo.asm`、`demo.rom.hex` 等；也可以用“文件…”精确指定文件名。
- 输出路径留空不会自动落盘；仍可用“导出当前页…”单独保存任一输出页。
- `test_workbench.py`、`test_editor.py` 与新增的 `tests/test_regressions.py` 覆盖：命令预览开关、三种目标的落盘、目录输出、文件夹浏览、Ctrl+S 保存、主题/目标设置持久化、GUI 目标切换与主题切换、格式化/自动缩进/括号配对/补全。
- v3.1 当前：**196 passed / 2 skipped**、`tools.check_logisim` 13 个程序 0 问题、`tools.check_docs` 与 `tools.check_architecture` 通过；主题切换与行号滚动在 QTest/offscreen 下验证；`python -m mycc --version` 输出 **3.1.0**。
- 限制：本机无 RARS jar，RARS 端到端仍按设计跳过；CPU21/Vivado 未在本环境执行。



### 轮次七（v3.1 演示与 GUI 修复，2026-11-02）

面向课堂演示的一轮修复，交互行为都在 offscreen Qt 下逐项验证：

| 主题 | 位置 | 内容 |
|---|---|---|
| 行号跟随滚动 | `mycc/gui/views.py` | 行号栏是独立控件，原先只在 `textChanged`/`cursorPositionChanged` 时同步；新增 `sync_number_scroll()` 并接到 `verticalScrollBar().valueChanged`，滚轮、拖动、翻页时行号与正文一起移动 |
| 滚轮防误改选项 | `mycc/gui/views.py` | `WHEEL_GUARDED`（`QComboBox`/`QCheckBox`/`QRadioButton`/`QAbstractSpinBox`/`QSlider`）上的滚轮事件一律拦截并转发给外层滚动区：不再误改 profile/目标/主题，侧栏仍可正常滚动；侧栏每个值控件另装一次过滤器兜底 |
| 自定义指令可回退 | `mycc/gui/workbench.py`、`mycc/gui/views.py` | 新增 `capability_snapshot()`（不抛异常、不做可行性校验）并导出 `core.expand`；ISA 非法（关掉 MV-ISA、ISA 文件损坏、设置里的旧项）时对话框仍能打开并提示如何修正；点“确定”若缺少 MV-ISA 必需指令，会列出缺失项并退回对话框 |
| 课堂演示脚本 | `demo.cmd`（新增） | 九段交互菜单（`demo.cmd a` 连播、`demo.cmd 3` 单段彩排），覆盖环境自检、ISA 数量、软件/硬件乘法对比、`--no-vshift` 代价、一键镜像、镜像预检、回归全绿、启动工作台 |
| 新增示例 | `examples/logisim/hannuo.c`、`examples/logisim/hello world.c` | 汉诺塔（`scanf` + `printf`，Logisim ROM 724 字）与最小 `printf("hello world")`（ROM 81 字）；`tools.check_logisim` 现覆盖 13 个程序 |
| 代码风格 | `mycc/core/`、`mycc/gui/` | 统一为 black 风格排版（仅格式，无行为变化） |
| 示例调整 | `examples/compiler/compiler_demo.c` | 追加 `j = j << 10` 一行用于演示移位；保持 C 子集可编译（本子集不接受 `int i,j=1;` 这类逗号多声明符） |

验证：`pytest` **196 passed / 2 skipped**；`tools.check_logisim` 13 个程序 0 问题（ROM 272~956 / 上限 1024，RAM ≤ 644 字节）；`check_docs`、`check_architecture` 通过；行号同步与滚轮拦截在 offscreen Qt 下验证。



### 本分支做成了什么

一句话：**把一个“能编译 hello world”的教学编译器，変成一个能在真实自建 RISC-V 硬件上跑非平凡 C 程序的编译器，并且全程零手写汇编。**

| 维度       | `8a5d050`（起点）                 | `v3.1-ide`（现在）                                                                                             |
| ---------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 目标平台   | 只产 GNU 汇编，需外部链接器         | 5 个可执行环境：通用、QEMU、CPU21 板卡、**Logisim 课堂 CPU**、**RARS**                          |
| 镜像导出   | 无                                  | 命令行一条命令直出 `v2.0 raw` 的 ROM/RAM 镜像，不依赖 Java、不依赖 GNU 工具链                             |
| I/O        | 只能输出；每次 ecall 都停机         | **标准 RISC-V 系统调用**（`a7=10/11/12`），打印与读键盘都不停机，同一份 `.asm` 丢进 RARS 行为一致 |
| 文本       | 不支持字符串，只能手写 `int` 数组 | **字符串字面量**（`.data` 里去重存放）                                                              |
| 格式化 I/O | 只能 `printint`/`printhex`      | **`printf` / `scanf`**，编译期展开、参数全程校验                                                  |
| 硬件验证   | 无                                  | 在自己的 Logisim CPU 上**实测通过**：`printf` 上屏、`getchar` 读键盘、0/1 背包 DP 算出正确答案    |
| 测试       | —                                  | **185 个自动化测试**，语句覆盖 **91%**，含与真 RARS 的逐字编码对照                              |

四个技术难点都是“现有工具里没有现成答案”的：

1. **没链接器、没 ROM 可读数据**的哈佛结构上，如何把全局变量和字符串字面量定位到 1024 字节 RAM。解法是有界的 `%lo` + 移位掩码重定位（`data_address_bits=10`），把地址真的落在 `0..1023`。
2. **指令集不全**时如何保证生成的代码每条都能执行。解法是在汇编层做一次能力驱动的降级（`lowering`），逐条规则记录“为什么选它 / 为什么跳过它”，并在镜像预检里反汇编验证。
3. **没有变参 ABI** 时如何做 `printf`/`scanf`。解法是把格式串在编译期展开成对助手函数的一次次直接调用——不增加硬件负担、不引入调用约定风险，而且参数个数和类型错误在编译期就报错。
4. **同一套代码同时跑仿真和硬件**。系统调用号、字符编码、堆栈初始化全部走标准约定，所以 RARS 与 Logisim 跑出一样的结果，现在还有自动化的端到端比对在盯着。

### 验证结果（v2.0 历史，2026-10-28）

> 以下为 v2.0 当时的结果记录；v3.0 的记录为 172 passed / 13 skipped，当前结果（196 passed / 2 skipped、ROM 272~956 等）见上方“轮次六”与“轮次七”。

| 项目                   | 结果                                                                                                     |
| ---------------------- | -------------------------------------------------------------------------------------------------------- |
| `\check.cmd`         | `171 passed, 1 skipped`，退出码 0                                                                      |
| 覆盖率                 | 语句 91%，门槛通过                                                                                       |
| 架构与文档门禁         | `architecture: ok`、`docs: preset table and JSON reference sets agree with core/isa.py`              |
| Logisim 镜像预检       | 11 个程序 0 问题（ROM 319~964 字 / 上限 1024；RAM ≤ 660 字节 / 上限 1024；v3.0 优化后为 272~956 / 644）                              |
| 编码器 vs 真 RARS      | 10 程序 × 3 指令集 = 30/30 逐字一致（新增示例前跑得的结果）                                             |
| 行为差分               | 同程序按 24 条指令集与 PF-01 编译，RARS 输出 10/10 相同（同上）                                          |
| CPU21 真实 RTL 回归    | 18/18 通过，外部 FPGA 工程 84 个文件只读未变更                                                           |
| **Logisim 实机** | 本次实测：`printf` 上屏、`getchar` 读键盘、0/1 背包输出 `max value for cap 70 = 3`（与 RARS 一致） |

未验证项：本机无 `qemu-riscv32`，执行与 GCC 对照未跑；Logisim 侧目前是行为级验证（指令集、寻址、容量）+ 实机功能验证，未覆盖时序余量与板级电平。

## 快速使用

以下命令在仓库根目录执行。CLI 只需 Python 3.11+ 和标准库，无需安装 GUI、GNU 工具链、QEMU 或 Vivado。

```powershell
python -m mycc --doctor

# CLI 输出父目录须先存在；生成物统一放在 build/
New-Item -ItemType Directory -Force build/demo | Out-Null
python -m mycc examples/compiler/compiler_demo.c -o build/demo/default.s

# 同一程序启用乘法指令，查看汇编变化及原因
python -m mycc examples/compiler/compiler_demo.c --enable mul -o build/demo/mul.s --dump-lowering-report

# 无需源文件也能查看最终 ISA
python -m mycc --dump-isa
python -m mycc --dump-isa-whitelist

# 课堂演示：交互菜单（a 连播、编号单段彩排、q 退出）
.\demo.cmd
.\demo.cmd a
.\demo.cmd 3
```

`compiler_demo.c` 定义 `square`，循环累加 0² 至 5²，再调用输出函数。预期运行输出为 `55` 加换行；上述命令只生成汇编，并未运行程序。

需要 GUI 和测试环境时：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt pytest coverage
.\launch.cmd
.\check.cmd
```

根目录 `.cmd` 自动优先使用本仓库 `.venv`；若 `.venv` 存在但没有 PySide6，`launch.cmd`/`scripts/launch.ps1` 会自动回退到系统 `python`。其余命令中的 `python` 指当前终端解释器；未激活环境时可替换为 `.\.venv\Scripts\python`。PowerShell 入口为 `scripts/launch.ps1`、`scripts/check.ps1`。若系统限制执行 `.ps1`，直接使用 `.cmd`，无需修改系统策略。

## 目录结构

```text
SoftwareEngineering/
├─ README.md                       使用、流程、实现和边界
├─ pyproject.toml                  包元数据、可选依赖及 pytest 配置
├─ requirements.txt / THIRD_PARTY.md  GUI 依赖 / 第三方说明
├─ launch.cmd / check.cmd          Windows GUI / 检查快捷入口
├─ demo.cmd                        课堂演示脚本（九段，可交互或单段）
├─ mycc/                           编译器软件
│  ├─ __main__.py / cli.py         模块入口、参数解析和文件读写
│  ├─ rars.py                      RARS 单文件导出、镜像 I/O 映射
│  ├─ encode.py                    内置汇编器：单文件汇编 → 机器码 → 镜像
│  ├─ core/                       标准库实现的七模块编译内核
│  │  ├─ types.py                 类型、AST、诊断、选项及结果结构
│  │  ├─ lexer.py                 C 文本 → Token
│  │  ├─ parser.py                Token → AST
│  │  ├─ sema.py                  作用域、符号和类型检查
│  │  ├─ isa.py                   ISA 预设、能力校验及指令回退
│  │  ├─ codegen.py               栈帧、表达式和控制流汇编生成
│  │  └─ driver.py                调度阶段并收集结果
│  └─ gui/                        PySide6 编译工作台
│     ├─ app.py                   启动与依赖检查
│     ├─ editor.py                自动缩进、括号配对、补全和格式化入口
│     ├─ formatting.py            纯文本 C 子集格式化器
│     ├─ completion.py            变量/函数/关键字补全候选
│     ├─ theme.py                 浅色/深色/高对比度主题与 QSS
│     ├─ workbench.py             状态、请求、设置、命令预览和导出逻辑
│     └─ views.py                 窗口、工具栏、侧栏、主题和结果展示
├─ runtime/                        与板卡无关的运行时
│  ├─ runtime.s                   软件算术与内存辅助函数
│  ├─ io.c                        printint / printhex / printstr 格式化输出
│  └─ input.c                     readint / readchar（需键盘的端口才链接）
├─ adapters/                       可选外部运行环境
│  ├─ cpu21/                      策略、ISA/MMIO、启动、VGA、链接、ROM 导出
│  ├─ logisim/                    课堂 CPU：译码 31 条、建模 24 条、有界 RAM 地址、无链接器
│  ├─ generic/                    通用裸机样例及占位 MMIO 配置
│  └─ qemu/                       Linux-user QEMU 启动和链接资产
├─ examples/
│  ├─ compiler/                   演示、函数、数组、控制流、指针和运算示例
│  ├─ cpu21/                      VGA、滚屏、栈保护及板卡自检示例
│  └─ logisim/                    课堂演示：可读文本输出、分段停钟版、背包 DP
├─ configs/isa/
│  ├─ presets/                    PF-01 至 PF-08 的 JSON 参考配置
│  └─ examples/board_v2.json       自定义 ISA 文件示例
├─ tools/                          python -m tools.* 开发工具
│  ├─ build.py                    GNU 汇编/链接及固件导出
│  ├─ check.py                    测试、覆盖率与可选外部验证
│  ├─ check_docs.py                README 预设表、JSON 参考集与 isa.py 一致性
│  ├─ check_logisim.py             镜像预检：指令集合规与 ROM/RAM 容量
│  ├─ check_rars.py                与 RARS 逐字对照汇编结果并对比运行输出
│  ├─ verify_cpu21.py             只读加载原始 RTL，运行固件回归
│  ├─ compare.py                  QEMU 中对照 mycc 与 GCC 行为
│  ├─ check_architecture.py       模块依赖边界检查
│  ├─ check_isa_consistency.py     编译配置与硬件能力对比
│  └─ lint.py / normalize_mnemonic.py  指令检查及助记符规范化
├─ scripts/                        PowerShell / Bash 辅助入口
├─ tests/                          编译、CLI、GUI、工具链及适配测试
│  └─ rtl/cpu21_program_tb.v       本软件维护的 RTL 验证 testbench
├─ docs/
│  ├─ README.md                   文档阅读顺序与版本索引
│  ├─ guides/                     当前范围及目录迁移说明
│  ├─ specs/requirements/         SRS 原始需求与历次修订
│  ├─ specs/design/               SDD 原始设计与历次修订
│  ├─ history/                    创意、决策、实施和兼容审计记录
│  ├─ verification/               纳入 Git 的历史结果与源码哈希
│  └─ images/workbench.png        工作台截图
├─ .github/workflows/              CI 检查
└─ build/                          自动生成，不纳入 Git
   ├─ demo/                       本说明中的编译输出
   ├─ reports/                    .coverage 和 coverage.json
   ├─ .pytest_cache/              pytest 缓存
   ├─ cpu21-verification/          可选 RTL 回归日志、ROM 和结果
   └─ archive/                    整理前的本地生成物归档
```

`.venv/`、`__pycache__/`、`build/` 属于本地环境或生成内容。源码、配置和文档由 Git 管理；`docs/verification/` 保存特定版本的验收证据，新运行的临时结果写入 `build/`。

ISA 文件描述“允许生成什么指令”，MMIO 文件描述“外设在哪里”。因此自定义 ISA 在 `configs/isa/`，地址配置在适配目录，二者不能混用。内置预设的实现源为 `mycc/core/isa.py`，`configs/isa/presets/` 是对应的 JSON 参考文件。

## 运行流程

### 从 C 到汇编：软件主流程

```text
CLI 参数 / GUI 编辑内容 + ISA 配置
                     │
                     ▼
            校验并形成最终可用指令集合
                     │
C 源码 → lexer → Token → parser → AST → sema → 已检查的 AST
                                                    │
                                                    ▼
                                       codegen 按 ISA 选择实现
                                                    │
                                                    ▼
                          汇编 + 诊断 + Token/AST/IR/Lowering 报告
                                                    │
                                  CLI 写文件 / GUI 展示与导出
```

1. **读取输入。** CLI 解析参数、读取 UTF-8 源文件和可选 JSON；GUI 从编辑器与 ISA 面板构建请求。默认 generic 环境和 PF-01。
2. **ISA 校验。** 合并预设或自定义集合及 enable/disable，检查必要能力。非法指令名返回配置诊断。
3. **词法与语法。** 识别关键字、标识符、常量和运算符并记录行列，建立函数、声明、语句与表达式的 AST。
4. **语义检查。** 建立符号及作用域，检查变量声明、参数、返回值和指针/整数操作等。
5. **生成汇编。** 分配栈帧、生成调用和分支，按 ISA 选择原生指令或软件回退。
6. **交付结果。** CLI 成功后原子替换 `.s`，失败不覆盖旧文件。GUI 保留上一次成功结果并标记失败或过期状态。

内核接收 `SourceFile`、`ISAProfile`、`CompileOptions`，返回 `CompileResult`；不读写文件、不创建窗口、不调用外部进程。文件操作属于 CLI/GUI，外部工具调用属于 `tools/`。

### 从汇编到运行：可选外部流程

```text
mycc .s + 软件辅助函数 + I/O + 目标启动代码
                         │
                         ▼
                  GNU as → .o → GNU ld → .elf
                                           │
                       ┌───────────────────┴─────────────────┐
                       ▼                                     ▼
                QEMU 执行与对照                    BIN / HEX / VH 等 ROM 输出
                                                             │
                                                             ▼
                                                   CPU21 RTL 仿真或人工集成
```

编译器负责表达式、控制流、调用约定和栈帧。真正运行还需 `_start`、初始栈、数据初始化、内存布局与外设函数。例如 `printint` 最终调用 `putchar`，其输出方式由环境决定。

CPU21 需要专门适配，因为它采用 Harvard 结构，ROM/RAM、VGA 协议和退出方式都有具体约束。仅选择相同 ISA 无法自动解决这些条件。`--profile cpu21` 只选择指令集合，`--target cpu21` 才加载适配策略。

输出为 GNU 汇编，使用 `.section`、`.type`、`%hi/%lo` 等语法，**不保证可直 接交给原来的 RARS JAR**。但 RARS 并不要自己写：`mycc --rars` 会输出一份 RARS 可 直接汇编并运行的单文件 `.asm`（重写 RARS 不认的指示字、内联软件算术辅助、把 `printint`/`printhex` 连同 `runtime/io.c` 一起内联进镜像，只把 `putchar`/`getchar`/`exit` 三个标准系统调用留成 ecall 存根）。它面向仿真，不包含板卡地址与 MMIO；需要真实目标布局时仍用 `tools.build`。

## 实现方式

| 部分       | 当前实现                                                                                                                        |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------- |
| 词法分析   | Python 正则扫描，跳过注释和空白，Token 保存源码位置                                                                             |
| 语法分析   | 声明/语句用递归下降，表达式按优先级解析，形成 AST                                                                               |
| 语义分析   | 函数与块作用域、符号和类型检查、调用及控制流约束；直接无终止递归（每条路径都再次调用自身）报 `W-SEMA-INFINITE-RECURSION` 警告 |
| 数据与调用 | 32 位 int、单层 int 指针、一维数组，ILP32 数据/调用约定                                                                         |
| 代码生成   | 遍历 AST 直接输出汇编；栈保存局部值及中间结果，s0 帧指针、16 字节栈对齐、a0–a7 参数寄存器                                      |
| ISA 回退   | 根据能力选择硬件指令、等价指令序列或运行时辅助调用                                                                              |
| 结果记录   | Token、AST、IR、Lowering、阶段耗时和诊断放入结果对象                                                                            |

当前是便于检查的直接代码生成器，没有独立优化器或复杂寄存器分配器。**IR 页面是代码生成过程中的结构化记录**，不是经优化后再交给独立后端的完整中间语言流水线。

例如 `int square(int n) { return n * n; }`：默认 PF-01 不含 `mul`，编译器调用 `__mulsi3`；加 `--enable mul` 后可生成 `mul`。前端仍解析同一个程序，变化发生在指令选择阶段，Lowering 报告说明原因。除法、取余、异或、移位等同样依据能力选实现；基本能力不足则拒绝配置。

`runtime/runtime.s` 提供软件算术和内存辅助函数，`runtime/io.c` 提供 `printint`/`printhex`/`printstr`（它们本身又建在 `putchar` 上），`runtime/input.c` 提供 `readint`/`readchar`（建在 `getchar` 上，所以只在有键盘的端口里链接）。外部环境只需提供 `putchar`/`getchar`/`exit` 三个标准系统调用。`printf`/`scanf` 不是函数：编译器在编译期把格式串展开成对上面这些助手的直接调用。观察 `.s` 无需链接，生成可执行程序时须补齐实际引用的符号。

CPU21 通过通用 `CodegenPolicy` 和外部函数签名注入 BSS 初始化、低地址约束及栈保护。固定 MMIO、容量、显存和故障协议留在适配目录，核心不加载板卡文件。

### GUI 工作台

v3.1 的 GUI 采用 IDE 式布局：顶部工具栏（新建/打开/保存、编译/停止、格式化、命令预览/环境自检/主题），左侧按“构建与输出 / 指令集 / 输出与外观 / 快捷操作”分组的设置栏，中间是带文件头、行号和当前行高亮的编辑器，底部是诊断表和输出页。菜单栏保留完整入口；工具栏不是菜单的替代品，而是常用命令的快捷方式。

编辑器支持 VSCode 风格的自动缩进：回车按当前 `{}`/`()` 层级对齐，`(`/`[`/`{` 自动配对，输入 `}` 自动回退一级，Tab/Shift+Tab 调整选中行；`Ctrl+Shift+F` 一键格式化整个当前文件（4 空格缩进、括号层级、分隔符空格、保留字符串和注释；紧凑单行函数会展开，数组初始化器保持原样）。补全通过 `Ctrl+Space` 或输入两个字符后自动弹出，候选来自当前文件中的变量/函数/参数、关键字和运行时助手。`Ctrl+S` 保存当前源文件；补全弹窗打开时也优先保存，不会把 `s` 输入到代码里。

所有 CLI 开关都在侧栏或菜单中有对应位置：目标、输出路径、写盘、RARS/Logisim 输出、栈顶、profile、ISA 文件、组/单条指令、`--no-lui`/`--no-vshift`、各 dump 页、`--stats`、环境自检、ISA 详情、CLI 开关对照。侧栏下方的“命令预览”按当前设置生成等价命令行，可一键复制。

主题有跟随系统、浅色、深色和高对比度四种，可从工具栏、视图菜单或侧栏切换；QSS 同时覆盖编辑器、侧栏、表格、页签、对话框和状态栏，设置写入 `~/.config/mycc/gui.json`（`schema_version=2`，旧板卡设置保留于 `legacy`）。

后台线程编译，主线程更新界面；源码或 ISA 修改后标记已有结果过期。“导出当前页”按当前结果页保存 `.s`/`.md`/`.txt`；勾选“编译成功后写入输出路径”时，通用目标写 `.s`，RARS 写单文件 `.s`，Logisim 写 `.asm` + `.rom.hex`（有初始化数据时再加 `.ram.hex`）。输出路径既可以是文件（“文件…”）也可以是文件夹（“文件夹…”或直接输入目录），文件夹会按源文件名生成 `demo.s`/`demo.asm`/`demo.rom.hex`。截图：[浅色](docs/images/workbench.png) / [深色](docs/images/workbench-dark.png)。

## ISA 与语言范围

`--profile` 选择内置预设，`--isa-file` 读取 JSON；`--enable/--disable` 可重复或用逗号分隔指令/组，disable 优先。兼容 `--no-lui`、`--no-vshift`。

| 预设                  | 指令数 | 用途                                                                |
| --------------------- | -----: | ------------------------------------------------------------------- |
| PF-01 / base          |     26 | 默认基础集合                                                        |
| PF-02 / base-nolui    |     25 | 无 lui 回退                                                         |
| PF-03 / base-novshift |     23 | 无寄存器移位回退                                                    |
| PF-04 / full-i        |     32 | 便利指令组合                                                        |
| PF-05 / i+m           |     29 | 硬件有符号乘除法                                                    |
| PF-06 / byteload      |     30 | 字节加载能力，不开放 char 类型                                      |
| PF-07 / all           |     39 | 本编译器指令范围上限                                                |
| PF-08 / logisim       |     24 | 硬件综合训练 Logisim CPU（设计报告表 1.1 的 28 条中可编码的 24 条） |
| cpu21                 |     32 | CPU21 编译器相关参考集合                                            |

常用组：`mul`、`divrem`、`m`、`xor`、`cmpbr`、`byteload`、`auipc`、`lui`、`vshift`。

```powershell
python -m mycc examples/compiler/muldiv.c --profile PF-01 --enable m -o build/demo/muldiv.s
python -m mycc examples/compiler/shifts.c --disable vshift -o build/demo/shifts.s --dump-lowering-report
python -m mycc examples/compiler/arrays.c --isa-file configs/isa/examples/board_v2.json -o build/demo/arrays.s
```

支持：int、单层 int*、一维数组、全局/局部变量、最多 8 参数、函数递归、if/else、while/for、break/continue、return、算术/位运算/比较/短路、自增减、赋值、下标、取地址/解引用和 sizeof。支持 `putchar('\n')` 形式的字符常量，但不支持 char 类型。字符串字面量 `"abc"` 是 `int` 数组（0 结尾）的地址，类型为 `int*`。

`printf`/`scanf` 由编译器在编译期展开：格式串必须是字面量，`%d`/`%x`/`%c`/`%s`（printf）与 `%d`/`%c`（scanf）各对应一次助手函数调用，参数个数和类型在编译期校验，写错直接报 `E-SEMA-FORMAT`：

```c
printf("max value = %d\n", best[cap]);       /* -> printstr + printint */
scanf("%d %d", &cap, &count);                /* -> readint + readint */
```

暂不支持：预处理、char、unsigned/volatile、结构体、类型转换、函数 指针、内联汇编、ISR、switch、?: 和 do-while。`printf`/`scanf` 不是变参函数，格式串不能是变量。启用更多 ISA 不会扩大 C 语言范围。

观察参数还有 `--dump-tokens`、`--dump-ast`、`--dump-ir`、`--dump-lowering-report`、`--stats`。源码诊断包含位置、阶段、错误码，并可附修复建议。

CLI 退出码：`0` 成功，`1` 编译失败，`2` 内部错误，`64` 参数/ISA 配置错误，`65` 源码读取/编码错误，`70` 输出写入失败，`130` 用户中断。

## 外部运行与验证

| 环境                                          | 所需工具                                                       | 提供内容和边界                                                                             |
| --------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| [CPU21](adapters/cpu21/README.md)              | RISC-V GNU 工具；RTL 回归另需 Vivado xvlog/xelab/xsim 和原 RTL | Harvard 启动、VGA、栈保护、MMIO 校验、ROM 导出；尚无物理上板证据                           |
| [Logisim 课堂 CPU](adapters/logisim/README.md) | **无**（自带汇编器与镜像编码器）                         | 译码 31 条（设计报告表 1.1）、1024 字 ROM / 1024 字节 RAM、无链接器；直接输出 ROM/RAM 镜像 |
| [generic 裸机](adapters/generic/README.md)     | RISC-V GNU 工具                                                | 统一可读代码/数据空间、占位外设的集成样例，使用前须核对硬件                                |
| [QEMU](adapters/qemu/README.md)                | RISC-V GNU 工具、qemu-riscv32；对照另需 GCC                    | Linux-user 启动和系统调用，不表示 FPGA 支持这些调用                                        |

```powershell
# RARS：单文件、可直接汇编并运行（仿真用，不含板卡地址）
python -m mycc examples/compiler/muldiv.c --rars -o build/muldiv.asm

# 硬件综合训练 Logisim CPU：一条命令出汇编 + ROM/RAM 镜像，不需要 Java 或 GNU 工具
python -m mycc examples/compiler/muldiv.c --target logisim -o build/demo/muldiv.asm
#   build/demo/muldiv.asm      可直接在 RARS（compact，data at 0）里跑
#   build/demo/muldiv.rom.hex  拖进 Logisim 的 ROM（上限 1024 字，现有示例 272~956 字）
#   build/demo/muldiv.ram.hex  程序有初值全局变量时才生成，拖进 RAM

# CPU21 完整固件：编译时选择地址配置
python -m tools.build examples/compiler/compiler_demo.c --target cpu21 --board-file adapters/cpu21/board.json -o build/cpu21-demo

# QEMU（需准备对应工具）
python -m tools.build examples/compiler/compiler_demo.c --qemu
qemu-riscv32 build/compiler_demo.elf
python -m tools.compare examples/compiler/compiler_demo.c

# 常规检查、可选 RTL 回归和严格检查
.\check.cmd
.\check.cmd --cpu21 --fpga-root D:\Xilinx\Project\risc-v
.\check.cmd --full

# 课堂演示前的两项确认（check_rars 需要 Java，缺少时自动跳过）
python -m tools.check_logisim
python -m tools.check_rars

# 对比编译器相关指令集合
python -m tools.check_isa_consistency adapters/cpu21/hw_caps.json --profile cpu21
```

CPU21 输出 `.s`、中间 `.o`、`.elf`、`.bin`、`.hex`、`.vh`、Logisim 镜像和 manifest。JSON 地址必须符合硬件实际译码；软件可配置不代表硬件地址随之改变。CPU21 无 UART，输出走 VGA，退出状态写 LED/SEG。

本次常规检查为 **196 passed、2 skipped**，语句覆盖率 79% 且门槛通过。检查包括错误恢复、输出保护、GUI offscreen、真实 GNU 汇编/链接及 54 组合 ISA 矩阵。本机缺少 `qemu-riscv32`，执行/GCC 对照仍未验证；`--full` 将缺工具作为失败。

CPU21 回归检查退出状态、VGA 600 个打包显存字、控制寄存器与栈故障行为，并对比外部工程前后文件哈希。本次整理后 **18 项回归全部通过，外部 84 个文件哈希一致**，见 [本次验证记录](docs/verification/layout-results-2026-10-26.json) 与 [CPU21 周期数据](docs/verification/cpu21-results-2026-10-26.json)。此前 [0.3.0 范围验收](docs/verification/scope-results-0.3.0-2026-10-26.json) 保留；新运行输出写 `build/cpu21-verification/`。

Vivado 的 `-testplusarg` 经 Windows 批处理包装后无法承载非 ASCII 路径，因此输出目录含中文时，回归会把 ROM 暂存到 `%TEMP%\mycc-cpu21-sim` 再仿真，结束后把结果回拷；调用方无需关心路径。

工具不回写 `D:\Xilinx\Project\risc-v`，不生成或下载 bitstream。仿真与物理上板属于不同验证层次。

## 文档和维护入口

完整索引见 [docs/README.md](docs/README.md)。现行需求按 SRS v1.2 通用基线及 v1.4 修订阅读，设计按 SDD v1.1 基线及 v1.3 修订阅读。CPU21 修订继续约束显式适配，历史记录和验收证据保留。

本次整理只改变文件位置、引用和说明。旧路径对应及生成物归档见 [目录整理记录](docs/guides/file-layout.md)。维护时：编译改 `mycc/core/`，界面改 `mycc/gui/`，运行环境改 `adapters/`，构建验证改 `tools/`，示例放 `examples/`，规范与记录放 `docs/`。修改内置 ISA 时同时核对 JSON 参考文件和测试。
