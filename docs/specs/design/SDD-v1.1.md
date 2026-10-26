> **Historical baseline (2026-10-26)**: original text preserved for traceability. The active baseline includes [SDD-MYCC-001 v1.2 CPU21 板卡适配修订.md](SDD-v1.2-cpu21.md); conflicting clauses are superseded by that revision.

# mycc 设计文档（SDD-MYCC-001 v1.1）

**对应需求基线**：SRS-MYCC-001 v1.2（实验 1 文档，本设计沿用其全部编号）  
**文档性质**：软件设计说明（架构 / 模块 / 流程 / 接口 / 数据 / 界面 / 非功能 / 异常 / 决策 / 追溯 / 验证 / 变更）  
**编号约定**：本设计不占用 SRS 已定义的前缀（FR/NFR/CN/IF/EX/PF/FM/AC/RS/SC/TC/D/AS/BG/RO/NG/DP）。本设计新增的编号前缀为：`MOD-`（模块）、`API-`（内部接口）、`EXT-`（外部接口）、`DS-`（数据结构）、`FL-`（流程/时序）、`DD-`（设计决策）、`DC-`（需求变更）、`LW-`（设计遗留项）、`TV-`（验证考虑）。凡引用需求，一律使用 SRS 原编号。

* * *

## §0 文档信息与修订记录

| 项 | 内容 |
| --- | --- |
| 文档编号 | SDD-MYCC-001 |
| 版本 | **v1.1** |
| 需求基线 | SRS-MYCC-001 v1.2 |
| 编制方式 | 个人完成（实验 2）；AI 辅助生成，已按 §12 的可验证性原则自查 |

### 修订记录

| 版本 | 修订说明 | 影响的章节 |
| --- | --- | --- |
| v1.0 | 首次发布；覆盖 12 个设计要素；提出需求变更 `DC-01`~`DC-06` | 全部 |
| **v1.1** | **①** `DC-04` **全文重写**：纠正原判断，把缺陷定位为"`NFR-703` 计时口径不明"，**撤销**矩阵范围收缩，明确 profile 矩阵在三环境均全量执行，并增补 5 分钟预算表；**②** `API-31`**/**`API-32` **命名统一**：§3 MOD-09 的 `compile_now`/`handle_result` 改回 `build_request`/`apply_result`，并新增 `API-xx` 命名一致性规则；**③ §11.2 与 §8 正文对齐**：拆解原"`NFR-1xx` → §8 性能一栏"的区间声明，新增 §8.1 覆盖完整性核对与遗留项 `LW-01`~`LW-07`，并在 §8 补齐` NFR-207`/`NFR-208`/`NFR-209`/`NFR-301`/`NFR-302`/`NFR-304`/`NFR-305`/`NFR-503` 的设计应对 | §0、§1.2、§3、§5.2、§8、§8.1、§11.2、§12 |

**本轮设计要素覆盖索引**
| 实验要求的设计要素 | 本文对应章节 |
| --- | --- |
| 1 架构设计 | §2 |
| 2 模块设计 | §3 |
| 3 关键流程设计 | §4 |
| 4 接口设计 | §5 |
| 5 数据设计 | §6 |
| 6 界面与交互设计要点 | §7 |
| 7 非功能设计 | §8（含 §8.1 覆盖核对与遗留项） |
| 8 异常与故障处理设计 | §9 |
| 9 设计决策与权衡 | §10 |
| 10 需求追溯矩阵 | §11 |
| 11 测试与验证考虑 | §12 |
| 12 需求来源与变更说明 | §1 |

* * *

## §1 需求基线说明与需求变更说明

### 1.1 需求基线来源

本设计**沿用实验 1 的 SRS-MYCC-001 v1.2** 作为唯一需求基线，不重列需求清单，以编号引用。基线的主要边界如下（不含全部条目）：
| 需求组 | SRS 出处 | 本设计承接章节 |
| --- | --- | --- |
| `FR-1xx` 编译驱动与 ISA 配置、`FR-10xx` 可选指令集机制 | SRS §4、§6.6、§6.9 | §3 MOD-06/07/08、§5、§6 |
| `FR-2xx`/`FR-3xx`/`FR-4xx` 前端三阶段 | SRS §4、附录 A | §3 MOD-01~05、§4 FL-01 |
| `FR-5xx` codegen 与 capability-driven lowering | SRS §4、§6.6(d)、`D-07` | §3 MOD-05、§10 DD-01 |
| `FR-6xx` 运行时与集成脚本 | SRS §4、§6.5 | §3 MOD-10~14、§5 EXT-01/02 |
| `FR-7xx` 诊断 | SRS §4、§6.4（含 `FR-708` 结构化字段） | §3 MOD-06、§6 DS-06 |
| `FR-8xx` 工程与测试 | SRS §4 | §3 MOD-15~17、§12 |
| `FR-9xx` 图形工作台 | SRS §4、§6.8（`IF-08`） | §3 MOD-09、§7 |
| `NFR-1xx`~`NFR-8xx` | SRS §5 | §8、§8.1、§12 |

> 说明：SRS §0.1 的 v1.2 变更清单与附录 C 的变更留档构成本设计与实验 1 之间的"接口"，本设计不重新定义需求，只在其上做设计展开；凡本设计认为基线存在缺陷的，一律走 §1.2 的显式变更流程，不做静默修改。

### 1.2 需求变更说明（本设计阶段提出的基线修正）

以下 6 项为设计阶段发现的 SRS v1.2 缺陷或未闭环处。每项给出：缺陷、改动、影响的需求编号。**未列入本表的 SRS 条目一律按原文执行。**

#### DC-01｜诊断码 `code` 缺少枚举定义（必须补齐）

*   **缺陷**：`IF-04` 把 `code` 定义为**必填**的"稳定诊断码"，并明确其用途是"供测试断言与文档索引"，`FR-708` 也要求结构化诊断携带该字段；但全文除 `IF-04` 实例中的 `E-UNSUPPORTED-CONSTRUCT` 外，**没有任何码表**。测试无法按码断言，`NFR-205`/`NFR-206` 的"按类统计"也无法自动化。
    
*   **改动**：在 SRS §6.4 增补一张诊断码表（约 24 条，形如 `E-LEX-UNEXPECTED-CHAR`、`E-PARSE-EXPECTED-TOKEN`、`E-SEMA-UNDECLARED-ID`、`E-PROFILE-MISSING-MVISA`、`E-PROFILE-NO-LOWERING`、`E-UNSUPPORTED-CONSTRUCT`、`W-SEMA-MISSING-RETURN`、`I-ICE`），并按 `stage` 字段分组；规定码**只增不改名**。
    
*   **影响**：`IF-04`、`FR-708`、`NFR-205`、`NFR-206`、`AC-06`、§11.2 追溯矩阵、`TC-701`~`TC-721` 的断言写法。设计侧对应：§6 DS-06。
    

#### DC-02｜助记符白名单与 objdump 输出之间缺"规范化"环节（接口边界不明）

*   **缺陷**：`FR-116` 规定 `--dump-isa-whitelist` 逐行输出助记符供 `lint.sh` 消费，`FR-609` 要求对 `objdump -d` 输出逐条比对；但 gas 伪指令（`li`/`la`/`mv`/`ret`/`j`）展开后，objdump 可能输出 `nop`（即 `addi x0,x0,0`）、`ret`（即 `jalr x0,0(ra)`）等**别名形式**，且 ABI 寄存器名（`sp`/`ra`/`a0`）与数字名并存。两侧不同源时 lint 必然误报，`AC-03` 判据会被污染。
    
*   **改动**：在 `IF-06` 增补一句"**规范化发生在 lint 的输入侧**"：`lint.sh` 在比对前把 objdump 助记符映射为基础助记符（`nop`→`addi`、`ret`→`jalr`、`j`→`jal`、`mv`→`addi`），映射表与新助记符**一律不得进入白名单**——否则 `FR-116` 的"`PF-01` 输出 26 行"判据立即失效。
    
*   **影响**：`FR-116`、`FR-609`、`FR-809`、`AC-03`、`NFR-209`。设计侧对应：§3 MOD-12、§5 EXT-01。
    

#### DC-03｜`--isa-file` 与 `--enable/--disable` 的组合优先级未定义（含 GUI 持久化语义）

*   **缺陷**：`FR-113` 只说"命令行选项在其之上做增删"，`FR-112` 只说"`--disable` 优先于 `--enable`"，但同一指令同时出现在**文件、**`--enable`**、**`--disable` **三处**时缺少统一裁决规则。更现实的连带问题是：`FR-905` 的 ISA 面板有"自定义"态，`FR-915` 要求持久化——若只存"最终指令集合"，用户从自定义态**无法回到预设**（预设被展开成了集合，丢失了"基线 + 差集"结构）。
    
*   **改动**：明确计算顺序为 `基线（--profile 或 --isa-file） → 并上 --enable → 减去 --disable → MV-ISA 校验 → lowering 可满足性校验`；并规定 `gui.json` 持久化的是**基线名 + 差集**（`{"baseline":"PF-01","enable":["mul"],"disable":["lui"]}`）而非最终集合。
    
*   **影响**：`FR-112`、`FR-113`、`FR-905`、`FR-915`、`FR-1004`（指纹定义需明确为"最终规范化集合的 SHA-256"）、`AC-09`。设计侧对应：§6 DS-07/DS-12、§4 FL-06。
    

#### DC-04｜`NFR-703`（`check.sh` ≤5 分钟）与三环境 × 9 profile 矩阵的执行预算**口径不明**

*   **缺陷**：SRS 附录 B 把 profile 矩阵列为 `FR-808` 的执行范围、把三环境列为 `check.sh` 的执行范围，但**未说明** `NFR-703` **的 5 分钟是对"单次** `check.sh` **执行"还是对"三环境合计"计时**。若按"合计"理解，则三环境各跑全矩阵必然超时；而 `AC-08`（干净环境一键复现全部结论、**不要求图形环境**）与 `AC-09`（P0，须由 `check.sh` 体现）又要求矩阵必须在无图形环境下执行——二者在"合计计时"这一读法下不可同时满足。
    
*   **改动**：
    1.  明确 `NFR-703` 的 5 分钟为**单次** `check.sh` **执行的端到端时间**；三个环境各自独立计时、**不相加**（`AC-12` 第 1 项只要求 E3 通过一次完整执行）。
        
    2.  **profile 矩阵（**`FR-808`**）在 E1/E2/E3 均全量执行**——它只依赖 `mycc` + `DP-01` + `DP-02`，与图形环境无关。本设计**撤销**任何"矩阵只在 E1 全量执行"的收缩写法（该写法会被读作静默放宽 P0 判据，为附录 C 所禁止）。
        
    3.  把"矩阵并行执行"由建议**固化为硬要求**，并定义并行单位：profile 矩阵与 lint 以 `(profile, 程序)` 为单位并行；`.s`/`.elf` 按 **profile 指纹**复用，不重复汇编链接。
        
    4.  环境差异**只允许出现在 GUI 一侧**：GUI 相关项在 E3 因 PySide6 缺失而 skip（`NFR-807`）；`AC-13` 在 E2（offscreen）验证，与 SRS 环境矩阵的归属一致；`gui` ≥60% 覆盖率阈值只在 E1/E2 断言，E3 报告为"不适用（PySide6 未安装）"。GUI 测试模块一律以 `pytest.importorskip("PySide6")` 守卫，缺失时整体 skip 而非 error。
        
    5.  增补 5 分钟预算表（见下）。
        
*   **影响**：`NFR-703`、`FR-804`、`FR-808`、`AC-08`、`AC-09`、`AC-12`、`AC-13`、`NFR-403`（`gui` 阈值的环境归属）、`NFR-807`。设计侧对应：§3 MOD-17、§8 `NFR-703` 行、§12 TV-04、§12 TV-10。
    

`NFR-703` **预算表**（度量环境见 SRS §5.0；"E1/E2/E3"为 4 路并行下的预估）
| 步骤 | 并行单位 | 串行预估 | E1 | E2 | E3 |
| --- | --- | --- | --- | --- | --- |
| 静态检查三件套（`FR-810`/`FR-812`/`FR-920`） | 3 个脚本 | 3 s | 3 s | 3 s | 3 s |
| 单元测试 + 覆盖率插桩 | 模块 | 65 s | 65 s | 60 s | 60 s |
| 端到端 B1~B4（编译→汇编→链接→qemu） | 程序 | 14 s | 14 s | 14 s | 14 s |
| **profile 矩阵 9×6 = 54 组合**（`FR-808`） | `(profile, 程序)` | 38 s | 12 s | 12 s | 12 s |
| ISA 一致性检查（`FR-614`） | — | 2 s | 2 s | 2 s | 2 s |
| lint（9 profile × B1~B5，`FR-609`/`FR-809`） | `(profile, 程序)` | 34 s | 11 s | 11 s | 11 s |
| `compare.sh` 对照（`FR-610`） | 程序 | 15 s | 15 s | 15 s | 15 s |
| offscreen GUI 逻辑测试（`FR-919`/`FR-920`） | 用例 | 25 s | 25 s | 25 s | skip |
| 覆盖率阈值断言（`NFR-403`） | — | 3 s | 3 s | 3 s | 3 s |
| **合计** |  |  | **≈150 s** | **≈145 s** | **≈120 s** |

> 三环境均 ≤150 s，对 300 s 阈值留 **≥2 倍余量**；余量用于覆盖 `NFR-702` 所指的环境敏感性（换机、换 Python 版本、换 PySide6 版本后需重测基线）。

#### DC-05｜`FR-905` 依赖 `FR-1005`，构成优先级倒挂

*   **缺陷**：`FR-905`（P1）要求勾选变化时提示"本次变更将影响 **N 处 codegen 决策**"，而 N 由 `FR-1005`（P2，且本身是"给定源码与两个 profile 做静态统计"的离线分析）给出。P1 需求引用 P2 数据源，`§8.1` 的优先级一致性校验对此未记录。
    
*   **改动**：把提示内容改写为**由 lowering 表静态可得**的量：① 受影响的可选组数；② 本次变更是否会使"当前源码所需的抽象操作"落入无 lowering 的分支（是/否/未知，未知时提示"下次编译确认"）；③ 提示"下次编译生效"。若确需 N 值，则把 `FR-1005` 的必要子集（仅 AOp 级差异计数）升为 P1，并在 SRS `§8.1` 一致性表中登记。
    
*   **影响**：`FR-905`、`FR-1005`、`FR-117`（Lowering 报告可选作数据源）、SRS §8.1、§11.2。设计侧对应：§3 MOD-08、§7.3。
    

#### DC-06｜`FR-919`/`FR-920`/`NFR-803`/`NFR-807` 的 P0 归口与 SRS §9.1 范围表写法不一致

*   **缺陷**：SRS `§8.1` 明确这四项为 P0（它们是"工作台定 P1 但不失控"的前提），但 `§9.1` 把它们列在"图形工作台（P1）"一行内，读者按范围表检索会误判优先级。
    
*   **改动**：在 SRS `§9.1` 把"工作台的 offscreen 可测性（`FR-919`、`FR-920`、`NFR-803`、`NFR-807`）"单独拆成一行并标注 P0；`§11.2` 的对应行一并拆分。
    
*   **影响**：SRS `§9.1`、`§8.1`、§11.2、`AC-13`、`NFR-403`（`gui` 覆盖率 60% 的技术前提）。设计侧对应：§3 MOD-09、§10 DD-04。
    

> **变更控制合规性**：以上 6 项均属"修正基线缺陷"，不新增功能、不放宽任何 P0 判据（`DC-04` 经 v1.1 修订后已明确**不收缩任何验证范围**）、不触碰 SRS `§9.3` 的 Out of Scope 边界、不修改语言子集定义（`CN-15`）、不在脚本中引入硬编码指令清单（`CN-16`），符合 SRS 附录 C 的变更禁忌。每项均已在 SRS §11.2 可反查到测试用例组，本设计在 §11 追溯矩阵中给出设计侧落点。

* * *

## §2 架构设计

### 2.1 分层视图

系统采用**四层 + 一外部层**结构。分层的第一原则来自 `CN-13`/`NFR-401`：**编译内核（core）零 I/O、零第三方依赖、零 Qt 对象**，它既是 CLI 与工作台的唯一共享实现（`FR-916`），也是 `AC-11`（GUI 与 CLI 逐字节一致）与 `NFR-803`（无显示环境可导入）能够成立的结构性前提。

```
┌──────────────────────────────────────────────────────────────────────────┐
│ L3  前端层（front-end，薄层，不含任何编译业务判断 · NFR-407）              │
│    cli/                        gui/                                       │
│    ├ argparse 解析 → options    ├ workbench.py（逻辑层，纯数据，可 offscreen）│
│    ├ 分派 → core.compile        ├ views.py（视图层，Qt 控件与信号连接）      │
│    └ 退出码映射                 └ app.py（启动探测 → FM-17 降级）            │
└───────────────┬──────────────────────────────┬───────────────────────────┘
                │ API-01（唯一入口）            │ API-01（同一入口）
┌───────────────▼──────────────────────────────▼───────────────────────────┐
│ L2  编译内核层 core（7 个模块，无循环依赖 · NFR-401 · CN-13）               │
│  isa ──→ driver ──→ lexer ──→ parser ──→ sema ──→ codegen                 │
│   (能力集)  (编排/诊断)   (Token)   (AST)    (符号表)   (AOp→lowering)      │
│    ▲ types（类型与常量求值）被 parser/sema/codegen 共用                      │
│  ── 禁止：写 stdout/stderr、读写文件、import cli/gui/PySide6、创建 Qt 对象   │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ 仅通过"文本产物 + 路径参数"与外界交互（IF-03 / IF-07）
┌───────────────▼──────────────────────────────────────────────────────────┐
│ L1  目标侧资产层（数据与汇编，不含 Python）                                  │
│  runtime/runtime.s   linker/link.ld   isa/*.json + isa/hw_caps.json        │
│  bench/B1~B9                                                              │
└───────────────┬──────────────────────────────────────────────────────────┘
                │
┌───────────────▼──────────────────────────────────────────────────────────┐
│ L0  构建与验证脚本层（可执行约束，把架构规则变成自动化检查 · FR-809~812）      │
│  build.sh  lint.sh  compare.sh  check_isa_consistency.sh  check.sh        │
│  tools/normalize_mnemonic.py（DC-02 的规范化层）                           │
└──────────────────────────────────────────────────────────────────────────┘
   ── 外部依赖（不属本系统，仅被调用）：DP-01 riscv-gnu-toolchain、DP-02 qemu、
      DP-06 PySide6（仅 L3 的 gui）、DP-08 硬件能力清单（数据文件，非可执行）
```

> 图例：`──→` 表示**控制/调用流**（谁是编排者）；§2.2 的表表示**依赖流**（谁 import 谁）。两图方向不一致处，以 §2.2 的依赖表为准（`driver` 依赖 `isa`，`isa` 不依赖 `driver`）。

### 2.2 组件职责与依赖关系

| 层 | 组件 | 职责（一句话） | 允许依赖 | 禁止依赖 |
| --- | --- | --- | --- | --- |
| L3 | `cli/` | 参数解析、退出码映射、`--dump-*` 输出、`--doctor` | `core`（仅 `API-01`/`API-05`）、stdlib | 第三方（`NFR-501`） |
| L3 | `gui/workbench.py` | 工作台状态、编译请求组装、诊断与文本导出的数据流 | `core`（仅对外接口） | 任何 Qt 控件类型、`cli` |
| L3 | `gui/views.py` | 控件构造、信号槽连接、渲染 | `workbench.py`、PySide6 | `core` 内部模块 |
| L2 | `core/driver` | 编译编排、诊断汇聚（Reporter）、退出码/异常归一化 | 其余 6 个 core 模块 | 文件 I/O、`print` |
| L2 | `core/lexer` | 源码 → Token 流，含行列与 UTF-8 处理 | `types`（无） | `sema` 及之后 |
| L2 | `core/parser` | Token → AST（递归下降 + 优先级爬升） | `lexer`、`types` | `codegen` |
| L2 | `core/types` | 类型对象、类型宽度/对齐、编译期常量求值 | 无 | 其余 core 模块 |
| L2 | `core/sema` | 符号表三级作用域、类型检查、子集外构造诊断 | `parser`、`types`、`driver.Reporter` | `isa`（`FR-415`！） |
| L2 | `core/isa` | profile 载入/校验/派生、能力谓词、指纹、白名单、**ISA 影响分析（**`API-24`**，见 MOD-08）** | stdlib（`json`/`hashlib`） | `codegen` |
| L2 | `core/codegen` | AST → AOp 序列（IR）→ lowering 选择 → 汇编文本 | `sema`、`types`、`isa` | `parser` 内部符号 |
| L1 | `runtime/`、`linker/`、`isa/*.json`、`bench/` | 目标侧资产 | — | Python 源码 |
| L0 | `scripts/`、`tools/` | 组装、检查、复现 | `mycc` CLI、DP-01、DP-02 | 硬编码指令清单（`CN-16`） |

**依赖方向的三条硬规则**（由静态检查脚本强制执行，见 §8）：

1.  `core` 的导入图不含 `cli`/`gui`/`PySide6`，`core` 内不出现对 stdout/stderr 的直接写入、不创建 Qt 对象（`CN-13`、`FR-810`）。**扫描归口**：`check_imports.py` 负责 import 图与 stdout/stderr 写入；`check_layering.py` 负责"不得创建 Qt 对象"（`FR-920`）。
    
2.  `sema` **不依赖** `isa`——即"哪些语言构造被接受"与 profile 无关（`CN-15`、`FR-415`、`FR-415` 的逐字节诊断判据）。
    
3.  `codegen` 对 `isa` 只做**能力查询**（`profile.has(mnemonic)`），不查询"当前启用了哪个组名"；所有指令选择必须走 lowering 表，不得出现以选项名为分支条件的代码（`FR-519`）。
    

### 2.3 部署与运行视图

**部署形态**：源码 + `requirements.txt` + 脚本，无打包分发（SRS §9.3）。目录结构：

```
mycc/
├─ core/            # L2 内核（7 模块；driver 为包，含 reporter/errors 子模块）
│  ├─ driver/  __init__.py  reporter.py  errors.py
│  ├─ lexer.py  parser.py  types.py  sema.py  codegen.py
│  └─ isa.py        # 含 MOD-08 的 impact()（API-24），不新开模块（NFR-401）
├─ cli/             # L3
├─ gui/             # L3：app.py  views.py  workbench.py（MOD-09 逻辑层）
├─ isa/             # L1 数据：PF-01..PF-07 内置由代码给出，*.json 为用户/硬件清单
│  ├─ board_v2.json  hw_caps.json
├─ runtime/runtime.s  linker/link.ld  bench/*.c
├─ scripts/  build.sh  lint.sh  compare.sh  check_isa_consistency.sh  check.sh
├─ tools/    normalize_mnemonic.py  check_imports.py  check_no_option_branch.py  check_layering.py
├─ tests/    unit/  e2e/  faults/  gui/  static/  matrix/
└─ requirements.txt
```

> 命名歧义提醒：SRS `FR-615` 规定数据目录为 `isa/`，而 `NFR-401` 规定内核模块名含 `isa`。二者不同物（一个是磁盘目录，一个是 `mycc.core.isa` 模块），设计上保留 SRS 名称，靠包路径区分，不引入新名字。

**运行视图（三种环境，对应 SRS 附录 B 的环境矩阵）**
| 环境 | 入口 | 参与组件 | 期望行为 |
| --- | --- | --- | --- |
| **E1** X11/Wayland + PySide6 | `./check.sh` / `mycc --gui a.c` | 全部 | 全量 profile 矩阵 + 手工清单（`NFR-806`） |
| **E2** `QT_QPA_PLATFORM=offscreen` | `./check.sh` | 全部（gui 逻辑层可驱动，视图不显示） | `FR-919`/`FR-920`/`AC-13` 通过；仅窗口管理器相关项 skipped |
| **E3** 无 `DISPLAY`/`WAYLAND_DISPLAY`、未装 PySide6 | `./check.sh` / `mycc a.c -o a.s` | L0/L1/L2 + `cli` | **全绿**（`AC-12` 第 1 项，P0）；GUI 项 skip；`mycc --gui a.c` → 单行中文提示 + 退出码 64（`FM-17`） |

**一次编译的运行时序（组件视角）**
`cli` →（`API-01`）→ `driver` → `isa`（载入+两项前置校验）→ `lexer` → `parser` → `sema` → `codegen`（含 lowering）→ `driver`（组装文本）→ `cli`（原子写出 `-o`）。**工作台走完全相同的路径**，只是 `Reporter` 的目的地由 stderr 写入器换成内存收集器（`FR-706`），`-o` 的写出动作换成把文本回填到汇编标签页（`FR-907`）。

* * *

## §3 模块设计

下表给出 18 个模块的边界、内部结构与对外接口。`core` 严格 7 个模块（`MOD-01`~`07`），满足` NFR-401`；诊断设施作为` driver `包的子模块，不额外增加 core 模块数；`MOD-08`不新开文件，而是`core/isa` 内的一个函数。
| ID | 模块 | 内部结构 | 对外接口 | 关键需求 |
| --- | --- | --- | --- | --- |
| **MOD-01** | `core/lexer` | `Tokenizer`（字符游标 + 行/列状态机）、`KEYWORDS`/`RESERVED_UNSUPPORTED` 两张常量表、UTF-8 BOM 与 `\r\n` 归一化前置器 | `tokenize(src: SourceFile, reporter) -> list[Token]`（`API-11`） | `FR-201`~`FR-210`；`A.3` 的"保留但不受支持"关键字表 |
| **MOD-02** | `core/parser` | 递归下降（声明/语句/块）+ 优先级爬升（表达式 14 级）、`ParseError` 恢复点 | `parse(tokens, reporter) -> Program`（`API-12`） | `FR-301`~`FR-314`、附录 A.1/A.2/A.4 |
| **MOD-03** | `core/types` | `Type` 单例（`INT`/`INT_PTR`/`VOID`/`ArrayType(n)`）、`size_of`/`align_of`、`ConstEvaluator`（`sizeof`、算术/移位/比较、除零检测）。**另承载** `Reporter` **协议与** `Diagnostic` **的定义（见** `DD-02`**）** | `type_of(node)`、`eval_const(expr) -> int | None` | `FR-404`、`FR-410`、`FR-414` |
| **MOD-04** | `core/sema` | `SymbolTable`（全局 → 参数 → 块，链式作用域）、`Checker`（逐节点访问器，与 AST 节点一一对应）、子集外构造特判表 | `analyze(prog, reporter) -> TypedProgram`（`API-13`） | `FR-401`~`FR-415`；**不 import` isa`** |
| **MOD-05** | `core/codegen` | ① `FrameLayout`（局部变量槽、16 字节对齐、`s0` 基准）；② `Linearizer`（AST → `AOp` 列表，即 `--dump-ir` 的内容）；③ `LOWERING_TABLE`（只读数据结构）；④ `Emitter`（`AOp` → 汇编文本，伪指令使用受 `IF-03` 约束） | `generate(typed, profile) -> AsmText`（`API-14`）、`lowering_report() -> list[LoweringChoice]` | `FR-501`~`FR-521`；`IF-06(d)`的 11 行对照表是`LOWERING_TABLE` 的**直接来源** |
| **MOD-06** | `core/driver`（包） | `driver.py`（编排 + 阶段计时）、`reporter.py`（`Reporter` 的 CLI/内存两种实现 + 单一格式化函数）、`errors.py`（异常层次） | `compile(src, profile, reporter, options) -> CompileResult`（`API-01`）、`format_diagnostic(d) -> str`（`API-03`） | `FR-101`~`FR-119`、`FR-701`~`FR-708` |
| **MOD-07** | `core/isa` | `ProfileLoader`（内置 `PF-01`~`PF-07`+`IF-07 `JSON 校验）、`CapabilitySet`（`frozenset[str] `+ 组标记）、`Fingerprint`、`Feasibility`（MV-ISA 校验 + lowering 可满足性） | `load_profile(opts) -> ISAProfile`（`API-21`）、`profile.has(m)`、`profile.groups()`、`profile.fingerprint()`、`whitelist(profile) -> list[str]` | `FR-111`~`FR-118`、`FR-1002`~`FR-1004`、`IF-06`、`IF-07` |
| **MOD-08** | ISA 影响分析（**落在** `core/isa` **内，不是独立模块**） | 由 `LOWERING_TABLE` 反查"某 AOp 的守卫涉及哪些助记符/组"，供 GUI 面板与 CLI 的 `--dump-isa` 复用 | `impact(profile_a, profile_b) -> ImpactReport`（`API-24`） | `FR-905`（按 DC-05 修订后的口径） |
| **MOD-09** | `gui/workbench.py`（逻辑层，P0 可测） | `WorkbenchState`（当前文件、来源文本、profile 基线+差集、最近一次成功结果、最近一次编译结果）、`build_request()`、`apply_result()`、`export_asm_diag_lowering()`、`build_run_command()` | `build_request(state) -> CompileRequest`（`API-31`）、`apply_result(state, res) -> UiModel`（`API-32`）、`export_asm_diag_lowering(state) -> tuple[str, str, str]`（`API-33`）、`build_run_command(state) -> list[list[str]] | None`（`API-34`） | `FR-919`、`FR-920`、`FR-906`、`FR-907`、`FR-910` 的命令组装、`FR-915` 的序列化 |
| **MOD-10** | `gui/views.py` + `app.py`（视图层） | `MainWindow`（`QSplitter` + 编辑器 + 诊断表 + `QTabWidget`）、`ProfilePanel`、`EditorView`、`DiagnosticTable`、`RunTab`、`json` 持久化、启动探测 | 无对外编程接口（仅信号槽） | `IF-08`、`FR-901`~`FR-918` |
| **MOD-11** | `runtime/runtime.s` | `_start`、`putchar`、`printint`、`printhex`、`exit`、`memcpy`、`memset`；软件乘除法与移位三件套包在 `.ifdef HAVE_MUL`/`HAVE_DIVREM`/`HAVE_VSHIFT` 内 | 汇编符号（`IF-05`） | `FR-601`~`FR-607`、`FR-613`；`D-11` 的边界语义 |
| **MOD-12** | `scripts/build.sh` + `linker/link.ld` | `.c→.s→.o→.elf→.hex/.bin` 流水线；依据 profile 传 `--defsym`；`--mno-relax` | 命令行（`API-41`） | `FR-608`、`FR-611`、`FR-612`、`CN-16` |
| **MOD-13** | `scripts/lint.sh` + `tools/normalize_mnemonic.py` | 白名单取自 `--dump-isa-whitelist`；objdump 输出先规范化（DC-02）再逐条比对；越界时打印地址/助记符/所属函数 | 命令行（`API-42`） | `FR-609`、`FR-809`、`AC-03`、`CN-16` |
| **MOD-14** | `scripts/check_isa_consistency.sh` | profile 能力集 vs `isa/hw_caps.json` 的集合比对，输出两侧差集 | 命令行（`API-43`） | `FR-614`、`DP-08`、`AC-10` |
| **MOD-15** | `scripts/compare.sh` | mycc 产物 vs `gcc -march=rv32i` 产物在 qemu 上比对 stdout/退出码 | 命令行（`API-44`） | `FR-610`、`AC-02`、`RS-05` |
| **MOD-16** | `tools/` 静态检查四件套 | `check_imports.py`（`FR-810`：import 图 + stdout/stderr 写入）、`check_no_option_branch.py`（`FR-519`，对 `codegen.py` 做 AST 扫描）、`check_layering.py`（`FR-920`：逻辑层不引用控件类型、不创建 Qt 对象）、`check_dag.py`（导入图无环，`NFR-401`） | 命令行（`API-45`） | `FR-519`、`FR-810`、`FR-812`、`FR-920`、`NFR-401` |
| **MOD-17** | `scripts/check.sh` | 串联静态检查 → 单元 → 端到端 → profile 矩阵（并行）→ 一致性 → lint → 对照 → 覆盖率 → offscreen GUI；三环境均全量执行（DC-04）；GUI 测试以 `importorskip("PySide6")` 守卫 | 命令行（`API-46`） | `FR-804`、`AC-08`、`AC-09`、`AC-12`、`NFR-703` |
| **MOD-18** | `cli/` | `argparse` 子命令、退出码映射表、`--doctor` 探测、`--version` 固定字段序输出 | 命令行（`IF-01`） | `FR-101`~`FR-119`、`FR-813`、`NFR-503` |

### 3.1 关键模块的内部结构要点

**MOD-05** `codegen` **的三段式结构（本设计的架构核心）**

```
TypedProgram(AST)
   │  Linearizer：按求值顺序展开为栈式三地址序列
   ▼
list[AOp]  ←── 这就是 --dump-ir 的内容（FR-103、FR-908）
   │  Selector：对每个 AOp，在 LOWERING_TABLE[aop] 中取"首个 guard 成立"的规则
   ▼
list[Emitted]  +  list[LoweringChoice]
   │  Emitter：寄存器名/标签/段/`.globl` 渲染；伪指令展开结果必须仍在 profile 派生集内（IF-03）
   ▼
AsmText  → 原子写 -o 路径（FR-106）或回填 GUI 汇编标签页（FR-907）
```

**为什么把"IR 定义在 AOp 上"而不是在 IR 里就直接选指令**：AOp 是"语言语义"的表示，与 profile 无关；只有 Selector 阶段才引入目标 ISA 知识。这使得 `sema`/`codegen` 前段完全不感知 profile（与 `FR-415` 的精神一致），并使 `FR-519`（不得以选项名分支）在结构上**不可能被违反**——因为控制流里根本没有可分支的选项对象。此点作为设计决策 `DD-01` 记录于 §10。
`LOWERING_TABLE` **的数据形状**（对应 `FR-520`/`FR-521`、`IF-06(d)`）：

```python
# 每条规则：guard（能力谓词）→ expand（AOp 序列模板）→ reason（为何未走首选路径）
LOWERING_TABLE: dict[AOpKind, tuple[LoweringRule, ...]] = {
    AOpKind.MUL: (
        LoweringRule(guard=lambda p: p.has("mul"), expand="mul {rd},{rs1},{rs2}", reason=""),
        LoweringRule(guard=lambda p: True,          expand="call __mulsi3",        reason="'mul' not in target ISA"),
    ),
    AOpKind.XOR: (
        LoweringRule(guard=lambda p: p.has("xor"),  expand="xor {rd},{rs1},{rs2}", reason=""),
        LoweringRule(guard=lambda p: True,          expand="(a|b)-(a&b) 三条",     reason="'xor' not in target ISA"),
    ),
    # …共 11 个抽象操作族（IF-06(d) 的 11 行），每条至少保留一条无守卫兜底规则（FR-520）
}
```

**MOD-06** `driver` **包的分工**：`reporter.py` 只做三件事——收集 `Diagnostic`、提供 `has_error()`、**用唯一一个** `format_diagnostic()` **渲染文本**。CLI 与工作台共享该函数，这是 `CN-11`/`FR-906` 的"诊断文本逐字一致"以及 `AC-11` 第 3 项被判据化的**唯一实现路径**（两套渲染必然漂移）。
**MOD-09 逻辑层与 MOD-10 视图层的切分标准**（`FR-920`、`DD-04`）：凡不涉及具体控件类型、可以用纯 Python 值描述的计算，一律放逻辑层。具体包括：诊断按行列排序、跳转目标的定位计算（`line/col` → 字符偏移，含制表符按宽度 4 展开）、`build.sh`+`qemu` 命令的参数列表组装（`NFR-604` 要求"参数列表、不经 shell"）、`gui.json` 的读写与容错、汇编文本的"上次成功结果"标注。视图层只剩"把 `UiModel` 铺到控件上"与信号连接。

* * *

## §4 关键流程设计

### 4.1 FL-01｜编译主流程（含前置校验与异常分支）

```
[cli/gui] 组装 options（profile 基线 + enable/disable，DC-03 的优先级）
    │
    ▼
[driver.compile] ──① 载入 profile ──→ [isa]  失败 → E-PROFILE-* → 退出码 65 / 工作台诊断表
    │
    ├──② MV-ISA 校验（FR-114）        失败 → 退出码 64（缺 jalr 等），**未创建输出文件**
    ├──③ lowering 静态可满足性校验     失败 → E-PROFILE-NO-LOWERING，退出码 1，
    │       （遍历 LOWERING_TABLE，对每个 AOp 检查是否存在 guard 成立的规则）
    │      ★②③ 必须发生在任何源码解析之前（SRS §7 共性要求）
    ▼
[lexer] ──④ 词法 ──→ 错误? → 汇总（最多 20 条，FR-108）→ 退出码 1
    ▼
[parser] ──⑤ 语法 ──→ 错误? → 同上；此时可继续解析以汇报更多错误
    ▼
[sema]  ──⑥ 语义（不感知 profile）──→ 错误? → 退出码 1
    ▼
[codegen] ⑦ Linearizer：AST → list[AOp]        （--dump-ir）
    │      ⑧ Selector：逐个 AOp 选 lowering     （--dump-lowering-report）
    │      ⑨ Emitter：渲染汇编（含伪指令合规检查）
    ▼
[driver] ⑩ 若 has_error() → **不写文件**（FR-106、FM-08）
        否则 → 写临时文件 .mycc-tmp-XXXX → fsync → rename 覆盖 -o（原子提交，FM-11）
    ▼
退出码 0；stdout 为空（除非 --dump-*，FR-703）
```

**异常路径汇总**
| 分支 | 触发 | 行为 | 需求 |
| --- | --- | --- | --- |
| ① | profile 非法 JSON / schema 不符 / 未知字段 / 缺 MV-ISA | 只报 profile 错误，不进入词法阶段 | `FM-13`、退出码 65 |
| ② | `--disable jalr` 等 | 列出 MV-ISA 清单，退出码 64，无输出文件 | `FM-14` |
| ③ | 全部比较指令被禁用 | 列出抽象操作名 / 所需能力 / 当前禁用项 / 建议 | `FM-15`、`IF-04` 实例二 |
| ④~⑥ | 源码错误 | 诊断入 `Reporter`；`has_error()` 为真后禁止写文件 | `FR-106`、`FM-04`~`FM-08` |
| ⑩ | 磁盘满 / 无权限 | 退出码 70；临时文件清理 | `FM-02`、`FM-11` |
| 任意 | 未捕获异常 | 顶层兜底 → `internal compiler error:` + 退出码 2；工作台弹窗给等价 CLI（`FM-18`） | `FR-704`、`FR-913` |

### 4.2 FL-02｜诊断汇聚与两条出口

```
各阶段 ──report(Diagnostic)──→ Reporter（driver.reporter）
                                   │
              ┌────────────────────┴────────────────────┐
      CLI：StderrWriter                         GUI：MemoryCollector
       格式化文本 → stderr（FR-703）              结构化字段 → 诊断表（FR-906）
              │                                          │
      （FR-701/702/704 格式）                    双击 → 光标杆到 line:col（FR-906）
              └────────── 同一个 format_diagnostic() ──────┘
                        （保证 CN-11 逐字一致）
```

### 4.3 FL-03｜工作台编译回路（`SC-10`、`G-06`、`NFR-310`）

```
用户落笔 ──F5/工具栏"编译"──→ views 调 workbench.build_request()
                                   │  主线程：按钮切为"取消"，状态 COMPILING
                                   ▼
                        QThreadPool 中的 QRunnable（NFR-802）
                        ↳ 调 core.compile(..., reporter=MemoryCollector)
                                   │  协作取消标志：每阶段边界检查一次
                        finished 信号（主线程槽）
                                   ▼
                        调 workbench.apply_result(res) → UiModel
                                   ▼
              ┌── 成功 ─→ 更新汇编/IR/Lowering 标签页；清空诊断表；状态栏写耗时与行数
              └── 失败 ─→ 填充诊断表；**保留上次成功汇编并标注"上次成功结果"**
                              双击诊断行 → QTextCursor 定位 + ExtraSelection 高亮（FR-906）
```

*   **分支**：编译期间再按 F5 → 忽略（按钮此时是"取消"）；取消 → 置标志，`core` 在下个阶段边界停止，`Reporter` 已有的诊断保留并标注"已取消"（取消语义见 §9.4）。
    
*   **异常**：`core` 抛 `IceError` → 视图层捕获 → 对话框给"源码 + profile 描述 + 等价 CLI 命令行"，该命令行必须能复现（`FR-913`）；界面不退出。
    
*   **过期标注**：编译成功后用户改动 profile 面板 → 汇编区标注"内容已过期"（`IF-08` 交互规格）。
    

### 4.4 FL-04｜一键运行（`FR-910`、`NFR-604`、`NFR-605`、`FM-19`）

```
点击"运行" → workbench.build_run_command() 产出**两个参数列表**（不经 shell）：
    1) ["bash", "scripts/build.sh", src.s, "--profile", pname]
    2) ["qemu-riscv32", elf_path]
        │
        ▼
views 用 QProcess 依次启动；启动 30 s 单次定时器（默认，可配）
        │
   ┌────┴─────┬──────────────┬─────────────┐
  正常结束   非零退出      用户点"终止"    超时
   │           │              │              │
   └───────────┴──────────────┴──────────────┘
        → 运行输出标签页：命令原文 / stdout / stderr / 退出码（或"已取消"/"已超时终止"）
        → QProcess::kill()，无残留；窗口关闭时统一 kill 所有子进程（NFR-605）
   若 DP-02 缺失 → 标签页提示"运行不可用"，编译与诊断功能不受影响（FR-910 尾句）
```

### 4.5 FL-05｜无头/无依赖降级（`FM-17`、`AC-12`）

```
mycc --gui [file] → app.py 启动探测（三步，按 SRS §7 FM-17 顺序）
  ① 检查 DISPLAY / WAYLAND_DISPLAY（含 WSLg 会话判定）
      失败 → 打印一行中文提示 → 退出码 64（不得输出 Traceback / Qt 插件错误）
  ② try import PySide6
      失败 → 同上
  ③ 试建 QApplication（含平台插件加载）
      失败 → 同上
  成功 → 构建 MainWindow；若给了 file，按 FM-21 做"载入校验"（不存在/非 UTF-8/超 128 KiB
         时编辑器仍打开，问题落在诊断表首行，不阻断后续编译其他文件）
```

### 4.6 FL-06｜profile 变更与四处同源核对（`SC-07`、`CN-16`、`AC-10`）

```
① 编辑 / 选择 profile（内置 PF、--enable/--disable、--isa-file；DC-03 的裁决顺序）
② mycc --dump-isa                     → 核对指令数、分组、被禁项与替代路径
③ mycc --dump-isa-whitelist           → 供 ④ 消费（**唯一指令清单来源**）
④ build.sh --profile <同一份>         → runtime.s 的 --defsym 由同一 profile 派生
⑤ lint.sh --profile <同一份>          → 白名单来自 ③；objdump 输出先规范化（DC-02）
⑥ check_isa_consistency.sh            → profile 能力集 vs isa/hw_caps.json，不一致打印差集
   ★ 全链路**无任何一处硬编码指令清单**；新增板卡只新增 isa/*.json，Python 源码 0 行改动
```

### 4.7 FL-07｜扩展流程（两条，验证可扩展性）

*   **新增硬件变体**（`NFR-405`）：新增 `isa/board_v3.json` → 跑 `FR-615` 检查（不修改 Python 源码）→ 跑一致性与 lint。**不新增 lowering 规则**，因为规则按 AOp 而非按板卡组织。
    
*   **新增 lowering 规则**（`NFR-406`）：在 `LOWERING_TABLE` 的对应 AOp 元组中**插入一个条目**（守卫 + 展开 + 原因文本），不改 `codegen` 控制流；若是新增"能力组"，则同时在 `isa` 的组定义表登记（数据，非控制流）。两项扩展均不触发 `FR-519` 静态检查失败。
    

### 4.8 流程与模块/接口的对应速查

| 流程 | 调用方模块 | 关键接口 | 读写数据 |
| --- | --- | --- | --- |
| FL-01 | `cli`/`gui` → `driver` | `API-01`~`API-05` | `DS-09`、`DS-13` |
| FL-02 | 各阶段 → `driver.Reporter` | `API-02`、`API-03` | `DS-06` |
| FL-03 | `views` → `workbench` → `driver` | `API-31`、`API-32`、`API-01` | `DS-09`、`DS-10` |
| FL-04 | `views` → `workbench` → `QProcess` | `API-34`、`EXT-06` | `DS-13` |
| FL-05 | `app.py` | `EXT-05` | — |
| FL-06 | `cli` → `isa` → 脚本 | `API-05`、`API-21`、`EXT-01`、`EXT-03` | `DS-07`、`DS-11` |

* * *

## §5 接口设计

**编号段含义**（便于跨章定位）：`API-0x` 内核对外接口；`API-1x` 各编译阶段接口；`API-2x` `isa` 接口；`API-3x` 工作台逻辑层接口；`API-4x` 脚本命令行接口。`EXT-0x` 外部系统接口。

> 本表全部条目对应 SRS `§3.3` 的 `DP-01`~`DP-09` 与 `§6` 的 `IF-01`~`IF-08`，**无新增外部能力假设，未虚构任何第三方能力或参数**。

### 5.1 内部模块接口（core 对外）

`core` 对外只暴露 `API-01`~`API-05`；`gui`不得 import`codegen`/`parser `的内部符号（`FR-916`）。
| ID | 接口 | 输入 | 输出 | 错误约定 | 调用限制 |
| --- | --- | --- | --- | --- | --- |
| **API-01** | `compile(src: SourceFile, profile: ISAProfile, reporter: Reporter, options: CompileOptions) -> CompileResult` | `src` 为**内存中的文本 + 路径**（core 自身不读文件） | `CompileResult{asm: str, diagnostics: list[Diagnostic], stages_ms: dict, lowering: list[LoweringChoice], ir_text: str, tokens_text: str, ast_text: str}` | 源码错误**不抛异常**，经 `reporter` 汇报；仅在明确"选项/配置错误"时抛 `ProfileError`/`FeasibilityError`；内部缺陷抛 `IceError` | 纯函数式：同参数同结果（`FR-107`）；**不得**写文件、不得写 stdout；**可从 worker 线程调用、无 Qt 依赖、可重入、无副作用** |
| **API-02** | `Reporter` 协议：`report(d: Diagnostic) -> None`、`has_error() -> bool`、`error_count() -> int` | — | — | 实现方（CLI/GUI）自行决定去向 | 可在编译全过程任意阶段调用；同一实例被同一次编译的多个阶段共享（非线程安全，故一次编译绑定一个线程） |
| **API-03** | `format_diagnostic(d: Diagnostic) -> str` / `format_with_caret(d, src) -> str` | — | CLI 文本形式（`IF-04`） | — | **全局唯一**的文本渲染入口；纯函数，可在测试中直接调用 |
| **API-04** | `Driver.run(argv_like: list[str]) -> int`（CLI 专用薄封装，返回退出码） | 已解析的选项对象 | 退出码 | 映射表见 §5.4 | 供 `cli/` 与测试调用；不得被 `core` 内部调用 |
| **API-05** | `dump_*()` 系列：`dump_tokens/ast/ir/isa/isa_whitelist/lowering_report` | `CompileResult` 或 `ISAProfile` | 文本（与 CLI `--dump-*` 的 stdout **逐字节相同**） | — | GUI 的四个标签页与 `FR-911` 的导出**必须**调用此系列，不得自行拼接（`FR-908`） |
| **API-11** | `tokenize(src: SourceFile, reporter) -> list[Token]` | 已解码文本 + 行索引（`DS-01`） | `list[Token]`（`DS-02`） | 词法错误经 `reporter`（`E-LEX-*`），返回已识别的 token；不抛异常 | 不感知 profile（SRS §4 注）；需 `DS-01` 已完成 BOM 与换行归一 |
| **API-12** | `parse(tokens, reporter) -> Program` | `list[Token]` | AST（`DS-03`） | 语法错误经 `reporter`（`E-PARSE-*`）；嵌套超限报错而非 `RecursionError` | 递归下降 + 优先级爬升；深度以显式计数器控制（`NFR-207`） |
| **API-13** | `analyze(prog, reporter) -> TypedProgram` | AST | 带回填类型的 AST + 符号表（`DS-04`） | 语义错误经 `reporter`（`E-SEMA-*`、`E-UNSUPPORTED-CONSTRUCT`） | **不 import** `isa`（`FR-415`）；`--lang` 由 `options` 传入 |
| **API-14** | `generate(typed, profile) -> AsmText` / `lowering_report() -> list[LoweringChoice]` | `TypedProgram` + `ISAProfile` | 汇编文本（`DS-13`）+ 每条 AOp 的选择与被否决规则（`DS-08`） | `NoLoweringError`（`FM-15`） | 只做能力查询（`profile.has`），不得查询组名或选项名（`FR-519`）；同参数同输出（`FR-107`） |
| **API-21** | `load_profile(options) -> ISAProfile` | `PF 名 / --isa-file 路径 / enable 列表 / disable 列表` | `ISAProfile`（含 `instructions`、`groups`、`baseline_name`、`diff`、`fingerprint`） | `ProfileError(code, message, suggestion)`；未知字段报错并给最近合法名（编辑距离 ≤2） | 一次编译只调用一次；结果按指纹缓存（`FR-118`） |
| **API-22** | `ISAProfile.has(mnemonic) -> bool` / `.groups() -> frozenset[str]` / `.fingerprint() -> str` | — | 布尔/集合/十六进制串 | 不抛异常 | 纯函数；可在 lowering 表的 guard 内被高频调用（须为 O(1) 集合查询） |
| **API-23** | `check_feasible(profile) -> None | raise` | profile | 无 | 抛 `FeasibilityError`（缺 MV-ISA → 退出码 64；无 lowering → 退出码 1） | 必须在任何源码解析之前调用（`FR-114`） |
| **API-24** | `impact(profile_a, profile_b) -> ImpactReport`（MOD-08） | 两个 profile | `{changed_groups: [...], affected_aops: [...], may_block_compile: bool}` | 纯计算 | 由 `LOWERING_TABLE` 反查；不读源码（DC-05 修订后的口径） |
| **API-31** | `build_request(state) -> CompileRequest` | `WorkbenchState` 实例（编辑器文本、profile 基线+差集、选项） | `CompileRequest{src, profile_opts, options}` | 不抛；非法状态由调用方在 UI 侧提示 | 只能在主线程调用；纯函数式（不修改 state） |
| **API-32** | `apply_result(state, res) -> UiModel` | `WorkbenchState` + `CompileResult` | `UiModel{asm_text, diag_rows, lowering_text, status_line, stale_flags}` | **纯数据**，可在 offscreen 下断言 | 主线程调用；不引用任何 Qt 类型（`FR-920`） |
| **API-33** | `export_asm_diag_lowering(state) -> tuple[str, str, str]` | `WorkbenchState` | `.s` 文本 / 纯文本诊断 / Markdown 表格 | 无数据时返回空串 | 供 `FR-911`；与 `API-05` 的分工：`API-05` 供**标签页显示**（与 `--dump-*` 逐字节一致），`API-33` 供**另存/复制**（含 Markdown 转换） |
| **API-34** | `build_run_command(state) -> list[list[str]] | None` | `WorkbenchState` | 参数列表数组（**不是 shell 字符串**） | 缺 `DP-02` 时返回 `None`，由视图提示"运行不可用"（`NFR-604`） | 纯函数；不得拼接 shell 元字符 |

**命名一致性规则（**`API-xx`**）**：

1.  一个 `API-xx` 编号**只对应一个可调用对象**，编号与函数名在 §3、§4、§5 三处必须逐字一致。
    
2.  接口一律以 `f(state, ...) -> R` 的**函数**形式给出，`state` 为 `WorkbenchState` 实例——不在不同章节混用"绑定方法 / 自由函数"两种写法。
    
3.  引用旧名（`compile_now`、`handle_result`）视为文档缺陷；评审时按本条核对（`TV-13`）。
    

### 5.2 外部接口

| ID | 外部系统 | 接口形式 | 输入/输出 | 错误约定与调用限制 |
| --- | --- | --- | --- | --- |
| **EXT-01** | gas / ld / objdump / objcopy（`DP-01`） | 子进程命令行 | 输入：`IF-03` 的汇编文本；输出：`.o`/`.elf`/`.hex` | 必须能被 `-mno-relax` **无警告**汇编（`FR-512`）；`objdump -d` 的助记符在比对前经 `tools/normalize_mnemonic.py` 规范化（DC-02）；调用方为 `build.sh`/`lint.sh`/`compare.sh`，不经 shell |
| **EXT-02** | `qemu-riscv32`（`DP-02`） | `QProcess` 或脚本调用 | 输入：`-nostdlib` 链接的 ELF；输出：stdout/stderr/退出码 | 仅由 `FR-910`/`FR-912` 的显式点击或脚本触发；缺位不影响编译与诊断（`FR-910` 尾句）；运行期必设 30 s 默认超时 |
| **EXT-03** | profile JSON（`IF-07`）与 `hw_caps.json`（`DP-08`） | 文件读写（`json`） | 见 §6 DS-11 | 未知字段**报错**不忽略；未知指令名给编辑距离建议（`FM-13`）；两者同 schema，可直接做集合比对（`AC-10`） |
| **EXT-04** | `~/.config/mycc/gui.json`（`FR-915`） | 文件读写（`json`） | 见 §6 DS-12 | 缺失/损坏/未知字段 → 回退默认 + 状态栏提示，**不阻断启动**；目录不可写 → 只提示一次（`FM-20`） |
| **EXT-05** | PySide6 / Qt 平台插件（`DP-06`/`DP-07`） | Python import + `QApplication` | — | 仅 `gui` 层可见（`CN-14`）；失败走 `FL-05`；版本由 `requirements.txt` 锁定（`NFR-509`） |
| **EXT-06** | 子进程（`build.sh`/`qemu`/`lint.sh`） | `QProcess`，**参数列表**、不经 shell、命令模板用户不可编辑 | 命令原文 + stdout + stderr + 退出码 | 30 s 默认超时；可终止；关闭窗口统一 kill；**不残留**（`NFR-604`/`NFR-605`） |

### 5.3 `--dump-*` 与 `--doctor` 的输出格式约定

`AC-11` 第 2 项要求"标签页文本与 `--dump-*` stdout 逐字节一致"，因此这些文本**必须有唯一生成者**（§12 原则 1）：
| 输出 | 唯一生成者 | 格式骨架 |
| --- | --- | --- |
| `--dump-tokens` | `API-05.dump_tokens` | 每行 `line:col\tkind\ttext`，按出现顺序 |
| `--dump-ast` | `API-05.dump_ast` | 缩进两格的树形文本，节点名 + 位置 + （sema 后）类型 |
| `--dump-ir` | `API-05.dump_ir` | 每行 `序号\tAOp\t操作数...`，按 Linearizer 输出顺序 |
| `--dump-isa` | `API-05.dump_isa` | 指令总数 → 按 `IF-06(c)` 分组的清单 → 已启用组 → 被禁指令与替代 lowering（`FR-115` 四段） |
| `--dump-isa-whitelist` | `API-05.dump_isa_whitelist` | 每行一个基础助记符，**稳定排序、无重复、无别名**（`FR-116`） |
| `--dump-lowering-report` | `API-05.dump_lowering_report` | 每 AOp 一段：所选规则 + 原因 + 被否决条目及其否决原因 |
| `--stats` | `MOD-06` 的阶段计时 | stderr，每行 `阶段名\t毫秒` |
| `--doctor` | `MOD-18` | 每项一行：`<项> : ok |

**约定**：格式即"唯一生成函数的输出"；测试以该函数为唯一基准，**禁止在测试中重写格式**（否则出现两套渲染，`AC-11` 立即失效）。

### 5.4 错误约定：异常 → 退出码映射（`FR-105`、`IF-01`）

| 异常类型（`core/driver/errors.py`） | 触发 | CLI 退出码 | GUI 表现 |
| --- | --- | --- | --- |
| `SourceError`（词法/语法/语义/子集外构造） | `FM-03`~`FM-09` | 1 | 诊断表填充 + 双击跳转 |
| `NoLoweringError` | `FM-15` | 1 | 诊断表 + Lowering 报告标签页显示被否决规则 |
| `ProfileError`（读不到/非法 JSON/未知字段/未知指令） | `FM-13` | 65 | 诊断表 + profile 面板标红 |
| `FeasibilityError`（缺 MV-ISA / 组合不可满足） | `FM-14` | 64 | 同上，附修正建议（可直接复制） |
| `UsageError`（选项非法、缺输入、多输入） | `IF-01` | 64 | — |
| `ReadError` / `WriteError` | `FM-01` / `FM-02` | 66 / 70 | 诊断表 |
| `IceError` | `FR-704` | 2 | 对话框 + 可复现的等价 CLI 命令行（`FR-913`） |
| `GuiUnavailableError` | `FM-17` | 64 | 单行中文提示，无回溯 |
| `CANCELLED`（协作取消，非异常） | 用户点"取消" | — | 保留已有诊断，标注"已取消"（语义见 §9.4） |

**调用限制**：`core` 的任何接口不得接受"要写到哪个文件"之类的副作用参数；输出路径只出现在 `cli`/`build.sh` 层——这是 `NFR-404`（单元可测）与 `CN-13` 能被静态检查的落地方式。

* * *

## §6 数据设计

### 6.1 内存数据结构

| ID | 结构 | 关键字段 | 约束 | 对应需求 |
| --- | --- | --- | --- | --- |
| **DS-01** | `SourceFile` | `path`、`text`（已去 BOM、`\r\n` 归一）、`line_index`（行首偏移数组） | UTF-8；≤1000 行 / 128 KiB；`col` 按 **Unicode 码位**计 | `FR-206`、`FR-207`、`IF-02` |
| **DS-02** | `Token` | `kind`、`text`、`file`、`line`（1 基）、`col`（1 基）、`end_col`、`value`（字面量求值结果） | 标识符 ≤255；字面量 0~4294967295 | `FR-201`~`FR-209` |
| **DS-03** | `AST` 节点族 | 每节点含 `kind`、`pos(line,col,end_col)`、`children`、`type`（sema 回填）。节点种类为 A.1/A.2 的 1:1 映射：`Program`/`FuncDef`/`GlobalDecl`/`Param`/`Block`/`If`/`While`/`For`/`Return`/`Break`/`Continue`/`ExprStmt`/`LocalDecl`/`Assign`/`Binary`/`Unary`/`Postfix`/`Index`/`Call`/`Sizeof`/`Ident`/`IntLit`/`CharLit` | 文法见附录 A；嵌套上限 200/100 层（显式计数器）；`type` 在 sema 前为 `None` | `FR-301`~`FR-311`、`FR-410` |
| **DS-04** | `Symbol` / `SymbolTable` | `Symbol{name: str, kind: Global | Param | Local, sym_type: Type, offset: int |
| **DS-05** | `AOp`（IR 指令，即 `--dump-ir` 内容） | `op`（如 `MUL`/`XOR`/`BR_LT_S`/`CONST32`）、`args`、`dst`、`src_pos` | AOp 与 profile **无关**；共约 30 种；顺序由 AST 遍历序唯一决定 | `FR-103`、`FR-501`、`FR-517`、`FR-518` |
| **DS-06** | `Diagnostic` | `file`、`line`、`col`、`end_col`、`severity`、`code`（DC-01 的码表）、`message`、`note`、`stage` | `code` 必填且稳定；文本由 `format_diagnostic` 唯一渲染 | `FR-708`、`IF-04` |
| **DS-07** | `ISAProfile` | `baseline_name`、`enable`/`disable` 差集（DC-03）、`instructions: frozenset[str]`、`groups`、`fingerprint`（排序去重清单的 SHA-256）、`whitelist: tuple[str, ...]`（稳定排序），以及**派生字段** `diff_vs_default`**（相对** `PF-01` **的集合并/差）** | 恒为 RV32IM 子集、恒含 MV-ISA（9 条） | `FR-111`~`FR-116`、`CN-02`、`FR-1004` |
| **DS-08** | `LoweringRule` / `LoweringChoice` | 规则：`guard`、`expand`、`reason`；选择结果：`aop`、`chosen_rule`、`rejected: [(rule, why)]` | 每个 AOp 至少一条无守卫兜底规则；展开只用 MV-ISA + 基础组。**ISA 面板与** `--dump-isa` **的"被禁用指令及其替代 lowering"是该结构按 AOp 的投影，不是独立数据结构** | `FR-520`、`FR-521`、`FR-117` |
| **DS-09** | `CompileResult` | `asm`、`diagnostics`、`stages_ms`、`lowering`、四个 dump 文本 | 纯数据，可跨线程传递 | `API-01`、`FR-908`、`AC-11` |
| **DS-10** | `UiModel`（`API-32`） | 汇编文本与"上次成功/已过期"标记、诊断行、Lowering 文本、状态栏文本 | 不引用任何 Qt 类型 | `FR-920`、`AC-13` |
| **DS-11** | `CompileOptions` | `lang: list[str]`（默认空）、`dump: set[str]`、`out_path: str | None`、`profile_opts: {baseline, enable, disable, isa_file}`、`stats: bool` | `lang` 与 profile 正交（`CN-15`）；`out_path=None` 表示"只返回文本、不写文件"（供 GUI 与 `--dump-*`） |

### 6.2 磁盘数据结构

**DS-12｜profile / 硬件清单文件（**`IF-07`**，JSON）**

```json
{ "name": "board_v2", "description": "…", "schema_version": 1,
  "instructions": ["add","sub",…, "mul","xor"] }
```

| 字段 | 必填 | 类型 | 约束 | 违反时 |
| --- | --- | --- | --- | --- |
| `name` | 是 | string | `[A-Za-z0-9_-]{1,64}`，不与内置 `PF-01`~`PF-07` 冲突 | `FM-13`，退出码 65 |
| `description` | 否 | string | ≤200 字符 | 超长即报错 |
| `schema_version` | 是 | int | 必须为 `1` | 报错并提示升级 |
| `instructions` | 是 | string[] | 元素属于 `IF-06` 全集；**无重复**；**必须包含 MV-ISA 9 条** | 未知指令给编辑距离 ≤2 的建议；缺 MV-ISA 列出完整清单 |

> `isa/hw_caps.json`（`DP-08`）使用**完全相同的 schema**，因此 `AC-10` 的比对是纯集合运算；这也是 `AC-10` 能被一条脚本覆盖的前提。

**DS-13｜工作台设置文件** `~/.config/mycc/gui.json`**（**`FR-915`**）**

```json
{ "schema_version": 1,
  "profile": { "baseline": "PF-01", "enable": ["mul"], "disable": ["lui"] },
  "recent_files": ["/home/u/snake.c", "…"],
  "window": { "size": [1440, 900], "splitter": [620, 480] },
  "editor": { "font_size": 13 } }
```

| 约束 | 行为 |
| --- | --- |
| `recent_files` ≤10 条、按最近使用降序 | 超限截断 |
| 存**基线 + 差集**而非最终指令集合 | 保证可从"自定义态"回退到任一预设（DC-03） |
| 未知字段 / 截断 JSON / 字段类型不符 | 回退默认值 + 状态栏提示一次，**不阻断启动**（`FM-20`） |
| 目录不可写 | 只提示一次，后续静默 |
| **写入时机** | 窗口正常退出时一次性写出；面板勾选变化只改内存态。窗口异常终止导致丢失时按默认值回退（`FM-20`） |

**DS-14｜编译产物与临时文件**
| 文件 | 产生者 | 约束 |
| --- | --- | --- |
| `-o` 指定的 `.s` | `cli`/`driver` 的写出动作 | **原子提交**：同目录 `.mycc-tmp-*` → `rename`；失败路径不留残骸（`FR-106`、`FM-11`、`NFR-203`） |
| `.o` / `.elf` / `.hex` / `.bin` | `build.sh` | 段地址由 `link.ld` 固定（`CN-07`）；小端显式指定（`NFR-504`） |
| `bench/*.c` | 人工 | 单文件、≤1000 行 |

**DS-15｜内存映射与栈预算（承接** `CN-07`**、**`AS-03`**、**`CN-08`**）**
| 区域 | 地址范围 | 容量 | 放置内容 | 相关约束 |
| --- | --- | --- | --- | --- |
| IMEM | 由 `link.ld` 固定起始，与 CPU 的 IMEM 映射一致 | — | `.text`（代码 + 运行时库） | `CN-07`、`FR-611` |
| DMEM | `0x8000`–`0xBFFF` | 16 KiB | `.data`（有初值全局）、`.bss`（零初始化）、栈 | `AS-03` |
| 栈 | 栈顶由 `_start` 设定，向低地址生长 | 预算上限 **4 KiB** | 帧指针 `s0` 相对访问 | `CN-08`（16 字节对齐）、`FR-602` |
| 运行时库占用 | 属 `.text` | 预算 **< 1 KiB** | `IF-05` 的函数集合 | `AS-03`、`FR-613`（可按 profile 裁剪） |
| 游戏（B5）静态数据 | 属 `.data`/`.bss` | 预算 **< 2 KiB** | 全局状态与显示缓冲的软件副本 | `AS-03` |

> **已知风险与检测手段**：B5 的长递归与数组使用可能触及 4 KiB 栈上限；设计上以 `FrameLayout` 在编译期计算**最大静态帧深**并在超过阈值时给出警告，同时在验收清单中保留"连续运行 ≥10 分钟"作为动态兜底（`AC-05`）。

**DS-16｜测试数据集（测试期数据，非运行期）**：9 个 profile 定义（`PF-01`~`PF-07` + `custom-div-only` + `custom-nolui-mul`）× B1~B9 的（源码，预期 stdout，预期退出码）三元组；负例集（越界助记符、窄/宽 profile 敏感性、畸形 profile JSON）。

### 6.3 一致性策略

| 策略 | 机制 | 保证的需求 |
| --- | --- | --- |
| **单一事实来源** | profile 文件 → `isa` 载入 → 派生出：编译器能力集、`--dump-isa-whitelist`、`build.sh` 的 `--defsym`、`lint.sh` 的白名单、`runtime.s` 的条件汇编。**链路中任何一处不得出现字面指令清单** | `CN-16`、`AS-10`、`AC-10` |
| **指纹即缓存键** | 一切与 profile 相关的缓存以 `(规范化能力集合的 SHA-256)` 为键；禁用 `dict` 迭代序参与输出 | `FR-107`、`FR-118`、`FR-1004`、`NFR-201` |
| **产物顺序确定性** | 汇编文本的整体顺序由 **AST 遍历序**唯一决定：标签编号按函数/语句出现顺序分配、符号表与段输出前统一排序、`.globl` 按符号名字典序、十进制数值转换不使用本地化。**禁止**任何输出依赖 `dict`/`set` 迭代序 | `FR-107`、`NFR-201` |
| **原子写** | 临时文件 + `rename`；失败路径清理 | `FR-106`、`FM-11` |
| **文本单源** | 诊断文本、`--dump-*` 文本、汇编文本各只有一个生成函数（§5.3） | `CN-11`、`FR-906`、`FR-907`、`FR-908`、`AC-11` |
| **语言/ISA 解耦** | `sema` 不 import `isa`；语言子集由 `--lang` 与 P0 定义决定 | `CN-15`、`FR-415` |
| **设置容错** | 读失败 → 默认值；写失败 → 提示一次；写入时机固定为正常退出 | `FM-20`、`FR-915` |

* * *

## §7 界面与交互设计要点

### 7.1 角色 × 界面 × 关键交互

| 角色 | 主界面 | 关键交互 | 设计要点 |
| --- | --- | --- | --- |
| **RO-01 编译器开发者** | CLI + `--dump-*` + 工作台的 Lowering 报告/工具输出 | 改 lowering 表 → `check.sh` 回归；`--stats` 看阶段耗时 | `--dump-lowering-report` 必须输出**被否决的备选与原因**（`FR-117`） |
| **RO-02 应用开发者（写游戏）** | 工作台为默认入口 | `F5` 编译 → 双击诊断跳转 → 看汇编 → `F6` 运行 → 看 stdout，全程单窗口 | 回路 ≤15 s（`NFR-310`）；编译在 worker 线程，UI 不冻结（`NFR-802`） |
| **RO-03 验收教师/助教** | README + `check.sh` + 工作台演示 | 现场改一行分号 → 看诊断跳转；现场切 `EX-01 mul` → 看 `call __mulsi3` 变 `mul` | 现场必须能一键复现；**装不上 PySide6 时立即退回纯 CLI 做等价演示**（`SC-05` 异常流） |
| **RO-04 下游工具链** | 非人机界面（`.s` 文件 + ABI） | 无 | 输出必须能被 gas 无警告汇编、100% 落在当前 profile 派生集内（`FR-511`、`FR-512`） |
| **RO-05 教学演示观众** | **仅工作台**，只读观察 | 看"这一行 C 变成了这几条汇编、以及为什么" | Lowering 报告标签页与 ISA 面板必须是**演示用的一等公民**，不是调试附属品 |
| **RO-06 环境准备者** | `README` + `requirements.txt` + `--doctor` | 装依赖 → `mycc --doctor` → 一键复现 | `--doctor` 每项失败都必须给出**可直接复制的一条修复命令**（`FR-813`） |

### 7.2 工作台主窗口与状态机

布局按 `IF-08` 实现（菜单栏 / 工具栏 / `QSplitter`（编辑器 + ISA 面板）/ 诊断表 / `QTabWidget` / 状态栏），`FR-902` 已给出线框，本设计不重复，只补充**设计侧的关键约束**：

1.  **诊断表数据源是** `DS-06` **的结构化字段，不是文本解析结果**（`FR-708`/`FR-906`）。行列 → 光标定位由逻辑层的纯函数计算（可 offscreen 断言），含制表符按宽度 4 展开、Unicode 码位计数（`RS-09` 的对策）。
    
2.  **过期与保留语义**：编译失败时汇编区不清空，标注"上次成功结果"；profile 面板改动后标注"内容已过期"。避免"错误时界面全空"这一常见体验缺陷。
    
3.  **面板即数据**：ISA profile 面板的勾选态在逻辑层表示为"基线 + 差集"（`DS-13`），指令总数与差集字段直接取自 `DS-07`（含 `diff_vs_default`），不重复计算（`NFR-304`）。
    
4.  **所有外部命令不可编辑**：路径通过独立文件选择器提供，命令模板固定（`NFR-604`）；这是防止 `FR-910` 演化为"调试器配置面板"的结构性措施（`RS-19`）。
    

**界面状态机**
| 状态 | 允许操作 | 按钮文案 |
| --- | --- | --- |
| `IDLE` | 编译、运行、lint、编辑、改 profile | 编译 / 运行 |
| `COMPILING` | 取消、查看已过期结果、切标签页、滚动 | **取消** |
| `RUNNING` | 终止、切标签页、滚动 | **终止** |
| `GUI_UNAVAILABLE`（E3） | — | 不启动，单行提示 + 退出码 64 |

### 7.3 交互反馈的量化目标（设计侧承担）

| 交互 | 目标 | 设计手段 |
| --- | --- | --- |
| 冷启动 | ≤3.0 s | 延迟 import 重型子模块；窗口首帧不等待 profile 载入 |
| 编译期间主线程阻塞 | ≤200 ms | 编译在 worker 线程；结果通过信号槽一次性回传 `DS-09` |
| "看到错误 → 光标跳转" | ≤2 次点击 | 诊断表单表 + 双击即跳 |
| ISA 面板改动后的提示 | 立即 | 由 `MOD-08` 静态计算（DC-05 修订后的口径），不做源码级离线分析 |
| 回路总耗时 | ≤15 s | 编译 + `build.sh` + qemu 串行；避免重复进程启动（复用最后一次 profile 指纹） |

* * *

## §8 非功能设计

| 需求 | 设计应对 | 可度量目标 |
| --- | --- | --- |
| `NFR-101` 编译吞吐 | 单遍词法/语法；`LOWERING_TABLE` 在模块载入时预解析为闭包/查表；profile 载入与可行性校验合并为一趟；禁止在热路径做字典/字符串比较（`FR-118`） | 1000 行 ≤1.0 s（5 次中位数） |
| `NFR-102` 峰值内存 | Token/AST 不保留重复字符串（`intern` 标识符）；dump 文本按需生成（默认 `None`） | ≤256 MiB RSS |
| `NFR-103` 规模增长比 | 词法/语法/语义均为单遍线性；不使用会退化为二次的字符串拼接（统一 `list` + `join`） | 2000 行 / 1000 行 耗时比 ≤3.0 |
| `NFR-106` 诊断产出开销 | 格式化只在唯一函数 `API-03` 内发生，且**仅在被消费时**调用（CLI 边收边写；GUI 只在填充诊断表时格式化） | 1000 条错误相对空诊断的耗时增量 ≤1 ms/条 |
| `NFR-107` profile 阶段 | 校验与 lowering 预解析各一次，缓存键为指纹 | ≤5 ms |
| `NFR-108` 可选组开销 | 指令选择是**同一张表的查表**，与启用组数无关；选项只改变守卫结果 | `PF-07` vs `PF-01` 增量 ≤5% |
| `NFR-201`/`FR-107` 确定性 | 所有集合输出前排序；不使用时间/随机/`id()`；`dict` 迭代序不得进入产物（§6.3 的"产物顺序确定性"） | 连续 10 次 SHA-256 全同 |
| `NFR-202` 畸形输入不崩溃 | 顶层兜底；解析器不递归下降超过上限（用计数器而非依赖 Python 递归深度）；profile 解析按数据而非代码 | 1700 个畸形输入，退出码仅 0/1/64/65/66/70 |
| `NFR-203`/`FR-106` 失败不留残骸 | 原子写 + 失败路径清理；GUI 不写 `.s` 到用户目录（除显式另存） | 100 次失败编译后目录快照不变 |
| `NFR-204`/`FR-511` 产物合法 | Emitter 只从 lowering 的 `expand` 模板取指令；伪指令展开结果在做静态检查时按 profile 校验 | 100% 通过 gas + 同 profile lint |
| `NFR-205`/`NFR-206` 诊断质量 | `DS-06` 强制 `line/col/end_col/code`；子集外构造走统一模板（`FR-409`） | 定位率 100%；建议率 ≥90% |
| `NFR-207` 栈安全 | 表达式/块嵌套深度以**显式计数器**实现，不使用 Python 递归深度；超限产生 `SourceError` 而非 `RecursionError` | 边界（200/100 层）与超限各 ≥1 用例，两路表现均为规范诊断 + 退出码 1 |
| `NFR-208`/`NFR-209` profile 不变性与敏感性 | 跨 profile 的**全部**差异收敛到 `LOWERING_TABLE.expand`（`DD-01`），使"一致性"成为**只有一处可能出错**的性质；lint 白名单由 profile 派生（`CN-16`）；MOD-17 的矩阵与窄/宽敏感性负例 | 9 profile × 6 程序 stdout 逐字节一致；窄 profile lint 非零、宽 profile lint 为零 |
| `NFR-301` 上手时间 | README 的"源码→hex"最短路径；`--doctor` ≤1 分钟给出结论含**可直接复制的一条修复命令**（`FR-813`）；依赖安装不计入 10 分钟 | 未接触过项目者 ≤10 分钟完成首个 hex |
| `NFR-302` 单命令验收 | MOD-17 `check.sh` **无参数、无外部配置、无图形前提**（`DC-04` 修订后三环境均全量执行） | 1 条命令全绿 |
| `NFR-304` ISA 面板可读性 | ISA 面板为"数据视图"而非文档链接：直接显示指令总数与相对 baseline 的差集（字段来源 `DS-07`，含 `diff_vs_default`） | 试用者无需查文档即可说出总数与差集 |
| `NFR-305` 错误可定位性 | 诊断表单表 + 双击跳转（`FR-906`）；定位计算为逻辑层纯函数 | ≤2 次点击 |
| `NFR-310`/`NFR-311` 可用性 | `--doctor` ≤1 分钟给结论；README 依赖安装与 `FR-917` 的 CLI 对应表；`FL-04` 的 30 s 超时可终止 | 回路 ≤15 s；环境准备 ≤5 分钟（联网）/ 离线按 `NFR-506` |
| `NFR-403` 覆盖率 | `core` ≥80%/60%、`codegen`/`sema`/`isa` ≥90%、`cli` ≥70%、`gui` ≥60% —— 后者由 `FR-920` 的逻辑/视图分层与 offscreen 可测性支撑（`DD-04`）；`gui` **阈值在 E1/E2 断言，E3 因 PySide6 缺失报告为不适用** | `check.sh` 内断言（E1/E2） |
| `NFR-405` 扩展成本 | 新变体只加 `isa/*.json`（`FL-07`） | 修改 Python 源码 0 行 |
| `NFR-406` lowering 成本 | 规则即数据（`DD-01`） | 新增 1 个条目，控制流不变 |
| `NFR-407` 前端薄度 | `gui` 中零编译业务判断；逻辑层只做"组装 + 呈现" | `gui` + `cli` 行数 ≤ `core` 行数 |
| `NFR-501`/`CN-18` 依赖白名单 | `core`/`cli` 第三方集合为空；`gui` 恰为 `{PySide6}`；由 `check_imports.py` 每次回归扫描 | 集合等式断言 |
| `NFR-502`/`NFR-504` 可移植性 | 端序显式指定；不依赖 X11 专有特性；路径处理用 `pathlib` | Linux/WSL2 结果一致 |
| `NFR-503` 版本可复现 | `--version` 固定字段序：`mycc <ver> | target=rv32im-subset | profile=<baseline_name> | gui=<available|unavailable> | PySide6=<ver|none>`；字段取自 `ISAProfile.baseline_name` 与 `EXT-05` 的探测结果 | 目视；字段缺失即判失败 |
| `NFR-506`/`NFR-509` 离线与版本锁定 | `requirements.txt` 锁到补丁号；`--doctor` 明确报告"未附 wheel，可退回 CLI" | 断网容器实测 |
| `NFR-601`~`NFR-603` 安全 | 手写词法/语法（不 `eval`/`exec`）；profile 按数据解析；不引入任何网络调用 | 代码审查 + import 扫描 |
| `NFR-604`/`NFR-605` 子进程 | `QProcess` + 参数列表 + 超时 + `kill` + 窗口关闭统一回收（`FL-04`） | B9 死循环在 ≤32 s 被终止且无残留进程 |
| `NFR-703` 回归时效 | profile 矩阵与 lint 以 `(profile, 程序)` 为并行单位；`.s`/`.elf` 按 profile 指纹复用；三环境各自计时不相加（`DC-04`） | **单次** `check.sh` ≤5 分钟（预算表见 §1.2 `DC-04`，三环境预估 150/145/120 s） |
| `NFR-801`/`NFR-802`/`NFR-809` GUI 性能 | 延迟 import；worker 线程；大文件（>128 KiB）提示而不渲染全部 | 冷启动 ≤3.0 s；主线程阻塞 ≤200 ms；空闲 RSS ≤200 MiB |

**约束与假设的承接**：`AS-11`（PySide6 可安装、offscreen 可用）、`AS-12`（验收机允许预装、"装不上"不构成验收失败）、`AS-13`（WSL2 图形通道可不假设存在）在设计中体现为**三环境矩阵**与 `FL-05` 的降级路径；`CN-17`（CLI 功能集为 GUI 超集）在设计中体现为"`gui` 不实现任何 CLI 没有的能力"这一约束（`FR-917` 的一一对应表即为其可核对形式）。

### 8.1 覆盖完整性核对与遗留项

**规则**：§11.2 只声明 §8 **实际**给出设计应对的需求编号；未闭合的一律登记为遗留项 `LW-xx`，不得在追溯矩阵中宣称覆盖。这是对 v1.0 中「`NFR-1xx` 性能 → §8 性能一栏」这一区间写法的纠正（该写法声称覆盖 `NFR-101`~`NFR-108`，而正文缺 `NFR-103`~`NFR-106` 四行）。
**本轮补入 §8 的条目**：`NFR-103`、`NFR-106`、`NFR-207`、`NFR-208`/`NFR-209`、`NFR-301`、`NFR-302`、`NFR-304`、`NFR-305`、`NFR-403`（补环境归属）、`NFR-503`、`NFR-703`（改口径）。
| ID | 需求 | 优先级 | 未闭合原因 | 补充所需工作 |
| --- | --- | --- | --- | --- |
| `LW-02` | `NFR-105` B5 帧预算 ≤16.7 ms | **P0** | 与 `DD-01`（栈式生成、无寄存器分配）直接相关，属 SRS `RS-03` 自认最高风险项；目前**既无预算拆解也无取舍策略** | 补"每帧周期预算表（≈10⁶/60 周期 → 可用指令数）+ 可用杠杆（`EX-03`/`EX-04`、常量强度削减、`mul` 路径）+ 不达标时的取舍顺序"；并新增一条 `DD`，显式记录"不为 `NFR-105` 引入寄存器分配"的理由与替代路径 |
| `LW-01` | `NFR-104` 生成代码 ≤3× GCC `-O0` | P1 | 缺测量口径与达标手段 | 补 qemu TCG 插桩的计数口径，与 `LW-02` 共用预算模型 |
| `LW-03` | `NFR-103` 规模增长比 ≤3.0（**度量口径**） | P1 | §8 已给设计应对，但缺合成源码两规模版本的定义 | 定义 1000/2000 行的生成器与度量脚本 |
| `LW-04` | `NFR-106` 单条诊断产出开销（**度量口径**） | P2 | §8 已给设计应对，但未指定度量点 | 在 `API-03` 外层加计时打点 |
| `LW-05` | `NFR-303` 帮助可见性 ≤60 行 | P1 | 未定义 `-h` 的排版结构 | 规定帮助分组与 `PF-01`~`PF-07` 的一行说明格式 |
| `LW-06` | `NFR-402` 公开函数 docstring ≥95% | P1 | 未指定统计脚本 | 复用 `MOD-16` 的 AST 扫描设施 |
| `LW-07` | `NFR-702` 性能指标时间敏感性 | P1 | 未规定重测触发与基线更新方式 | 在 §12 `TV-11` 增加"换机/换版本即重测并更新基线"的触发条件 |

> **修补优先级**：`LW-02` 是唯一 P0 缺口，且它决定 B5 能否验收，应在写 `codegen` 之前先出预算模型；其余六项均为一行到一段的补充，可随对应模块一并补入。

* * *

## §9 异常与故障处理设计

### 9.1 分层异常体系

```
IceError                 ← 兜底（断言失败、未预期分支）      → CLI 2 / GUI 对话框（FR-913）
 ├─ ProfileError         ← 载入/校验/profile 内容            → CLI 65 / GUI 诊断表
 ├─ FeasibilityError     ← 缺 MV-ISA / 无 lowering           → CLI 64 或 1 / GUI 诊断表
 ├─ SourceError          ← 词法/语法/语义/子集外构造          → CLI 1  / GUI 诊断表
 │   ├─ LexError  ParseError  SemaError  UnsupportedConstructError
 ├─ IoError              ← 读 66 / 写 70                      → CLI 66/70
 └─ GuiUnavailableError  ← 启动前探测失败（FM-17）            → CLI 64，单行中文提示
```

**设计要点（消除 §5.1 与 §9.1 的表面矛盾）**：`SourceError` 家族的类**不作为控制流异常抛出**，而作为**诊断分类与退出码归类的载体**——阶段内部遇到源码错误时，构造对应的 `SourceError` 子类实例并交给 `reporter`，`driver` 在收尾时用其类型决定退出码；`API-01` 的"源码错误不抛异常"与本层次体系因此并不冲突。例外：`ProfileError`/`FeasibilityError`/`IceError`/`IoError`/`GuiUnavailableError` 是**真异常**（可中止编译），因为一次编译中它们只可能发生一次且不可继续。

### 9.2 故障模式 → 处理路径 → 恢复策略（按 SRS §7 的 21 条）

| 组 | FM | 检测点 | 处理路径与恢复 |
| --- | --- | --- | --- |
| 输入/输出 | `FM-01` `FM-02` | `cli` 打开/写临时文件 | 报错终止，无输出文件；用户改路径后重跑 |
| 编码/词法 | `FM-03` `FM-04` `FM-06` | `MOD-01` | 给字节偏移或行列 + 码点；`#` 走专门"不支持"诊断（不报"非法字符"） |
| 语法/语义 | `FM-05` `FM-07` `FM-08` `FM-09` | `MOD-02`/`MOD-04` | 含"期望/实际"；超上限（行数、嵌套、参数、标识符长度）一律**报错而非崩溃**，不触发 `RecursionError` |
| 编译期内部 | `FM-10` `FM-11` | 顶层兜底 / 原子写 | ICE 给最小复现提示；`FM-11` 静默保证输出文件原状，下次运行前清 `.mycc-tmp-*` |
| ISA 一致性 | `FM-12` | `lint.sh` / `check_isa_consistency.sh` | 报越界助记符地址或两侧差集；**流水线失败**，需人工修 profile 或补硬件 |
| profile | `FM-13` `FM-14` `FM-15` | `MOD-07` 的两项前置校验 | 全部在**任何源码解析之前**完成；三种退出码分别为 65/64/1；缺 MV-ISA 时列全 9 条清单；无 lowering 时列"操作/所需能力/当前禁用/建议"四要素 |
| 硬件与编译器错配 | `FM-16` | `check_isa_consistency.sh` | 打印两侧差集，非零退出；触发 `NFR-704` 的 5 工作日同步要求 |
| GUI | `FM-17` | `app.py` 三步探测 | 单行提示 + 64；**不输出 Traceback / Qt 插件错误细节** |
| GUI 运行中 | `FM-18` | 视图层广捕获 | 对话框给等价 CLI 命令行；界面存活可继续 |
| 子进程 | `FM-19` | `QProcess` 信号 + 定时器 | 显示命令/stdout/stderr/退出码或"已取消/已超时终止"；`kill` 且不残留 |
| 设置与载入 | `FM-20` `FM-21` | 逻辑层读写 / 载入校验 | 回退默认并提示一次；`--gui <file>` 的文件问题落到诊断表，**不阻断后续编译其他文件** |

### 9.3 共性恢复原则（设计的"全局不变量"）

1.  **失败不落盘**：任何失败路径都不创建/覆盖输出文件（`FR-106`），也不留临时文件（`NFR-203`）。
    
2.  **失败不降级能力**：GUI 的任一部分不可用，都不得使编译与诊断能力缺失（`FM-17`~`FM-21` 的共同约束）。
    
3.  **失败可复制地复现**：凡 GUI 内部错误，必须同时给出等价 CLI 命令行（`FR-913`）。
    
4.  **不残留资源**：子进程、临时文件、窗口关闭三者统一回收（`NFR-605`）。
    

### 9.4 协作取消的语义（补全 `FL-03` 的分支）

| 问题 | 约定 |
| --- | --- |
| 已收集的诊断是否计入 `has_error()` | 计入。取消后 `Reporter` 的内容保持原样，不追加"已取消"诊断（避免污染 `AC-11` 第 3 项的逐字比对） |
| 是否更新 dump 文本与"上次成功结果" | **不更新**。取消视为本次编译无产出，汇编区维持"上次成功结果"标注 |
| 是否置"内容已过期" | 不置。过期标记只由 profile 面板变更触发 |
| 是否可立即再次编译 | 可以。取消后状态机立刻回 `IDLE`，无残留 worker |

* * *

## §10 设计决策与权衡

SRS `D-01`~`D-13 `已记录需求级决策，本设计只补**设计级**决策（`DD-xx`），并标注其与 SRS 决策的承接关系。
| ID | 决策 | 备选方案 | 否决理由 | 承接 |
| --- | --- | --- | --- | --- |
| **DD-01** | IR 的指令集合定义为 **AOp（与 profile 无关的抽象操作）**，指令选择只在 Selector 阶段的 lowering 表里发生 | ① 在 IR 里直接选指令；② 让硬件侧提供多套汇编模板 | ① 会把 profile 知识渗入 IR 与 sema 前段，`FR-415`/`FR-519` 都变成"靠自觉"；② 把编译期问题推给硬件侧，违反 `AS-10` | `D-07`、`FR-519`/`FR-520` |
| **DD-02** | `Reporter` 协议与 `Diagnostic`（以及 `errors.py` 的异常层次）放在 `core/types.py`（已是叶子模块）；`driver/reporter.py` 只提供 CLI 与内存两种**实现** | ① 各阶段只接收 `reporter` 参数、不 import 任何 `driver.*` 符号；② 新建 `core/diag.py` 叶子模块；③ 维持 v1.0 的"放进 `driver` 包" | ③ 使依赖图成环（`driver → sema/parser → driver.Reporter`），违反 `NFR-401` 的"无循环依赖"与 §2.2 硬规则 1，且 `FR-810` 没有任何一条检查能发现该环；② 会使 core 模块数变成 8，直接违反 `NFR-401`。①可行但会导致各阶段的类型标注依赖鸭子类型，静态可读性下降 | `NFR-401`、`FR-706`、`CN-13` |
| **DD-03** | 诊断文本只有**一个**格式化函数 `format_diagnostic()`，CLI 与 GUI 都必须调用它 | GUI 自己拼接文本 | 两套渲染必然漂移，`CN-11`/`FR-906`/`AC-11` 第 3 项立刻失效 | `CN-11`、`FR-706`、`FR-906` |
| **DD-04** | `gui` 的切分标准定为"**是否可用纯 Python 值描述**"：能则入逻辑层（`workbench.py`），否则入视图层 | ① 全部写在 `MainWindow` 里，用手工清单代替测试；② 引入 `pytest-qt` + 图像比对 | ① `gui` 覆盖率退化为接近 0，`AC-11` 的三项逐字节比对无法自动化；② 超出 `CN-18` 白名单且像素级断言收益低 | `D-09`、`D-13`、`FR-920`、`AC-13` |
| **DD-05** | "运行"= `QProcess` 调 `build.sh` + `qemu`，**不内嵌仿真、不做调试器** | 内嵌一个 RISC-V 解释器以获得"单步/断点" | 与 `NG-09` 直接冲突；`FR-917` 要求"运行"必须存在 CLI 等价物，内嵌仿真无对应 CLI 形态 | `D-08`、`NG-09`、`RS-19`、`FR-910` |
| **DD-06** | 一切与 profile 相关的缓存以**指纹**为键；输出前对所有集合排序 | 以 profile 名字符串为键 | 名字相同不代表能力相同（用户可 `--enable` 覆盖内置名）；`FR-107` 的确定性会以极隐蔽的方式被破坏 | `FR-118`、`FR-1004`、`NFR-201` |
| **DD-07** | 把架构约束写成**可执行的静态检查**四件套：`check_imports.py`、`check_no_option_branch.py`、`check_layering.py`、`check_dag.py` | 靠代码评审与口头约定 | 约束一旦只存在于文档，实现期必然被侵蚀（`RS-18` 的同类风险）；四个脚本各自不到百行，成本远低于一次返工 | `FR-519`、`FR-810`、`FR-812`、`FR-920`、`NFR-401` |
| **DD-08** | 三环境**均全量执行** profile 矩阵；环境差异只出现在 GUI 一侧；`NFR-703` 按单次执行计时 | 三环境各跑全矩阵并**按合计**计时，据此收缩 E2/E3 的矩阵范围 | 收缩矩阵会被读作静默放宽 P0 判据（`AC-08`/`AC-09`/`AC-12` 第 1 项），为附录 C 所禁止；真正的缺陷是计时口径而非工作量（见 `DC-04` v1.1 修订） | `NFR-703`、`FR-804`、`AC-12`、`DC-04` |
| **DD-09** | `lint.sh` 的助记符规范化放在**输入侧**（`tools/normalize_mnemonic.py`），白名单保持"SRS 意义的 26 行" | 在白名单里加入 `nop`/`ret` 等别名 | 会使 `FR-116` 的"`PF-01` 输出 26 行"判据失效，并让白名单不再是"profile 派生集"的忠实表示 | `DC-02`、`FR-116`、`FR-609`、`AC-03` |
| **DD-10** | GUI 的 ISA 面板持久化"基线 + 差集"，不持久化最终集合 | 持久化最终指令集合 | 会丢失"从预设出发"的信息，用户无法回退到预设；也使 `FR-905` 的"自定义态"语义变得不可判定 | `DC-03`、`FR-905`、`FR-915` |
| **DD-11** | `dump_*` 文本的格式即"唯一生成函数的输出"；测试以函数为唯一基准，禁止在测试中重写格式 | 在测试里按文档骨架重新拼装期望文本 | 会出现第二套渲染器，"逐字节一致"的判据将退化为"两套实现互相对齐"，且 `AC-11` 无法定位失败原因 | `AC-11`、`FR-907`、`FR-908`、§5.3 |
| **DD-12** | 一个 `API-xx` 编号只对应一个可调用对象，且接口一律写成 `f(state, ...) -> R` 的自由函数形式 | 允许绑定方法与自由函数混用，编号在不同章节承载不同名字 | 会造成 §3/§4/§5 三处签名不一致（v1.0 中 `compile_now`/`handle_result` 与 `build_request`/`apply_result` 即为实例），直接命中"设计内部相互矛盾"这一判据 | §5.2 命名一致性规则、`TV-13` |

* * *

## §11 需求追溯矩阵

**读法**：每行给出需求（或需求组）→ 承接它的设计元素（模块 / 数据结构 / 接口 / 流程 / 决策）。约束类（`CN-xx`）作为横切关注点单列。凡"需求有、设计缺"的空洞项在此表中无处可藏，这是本表的设计目的。**P0 需求按单项列出**（区间合并只用于 P1/P2）。

### 11.1 功能需求 → 设计元素

| 需求 | 设计元素 | 备注 |
| --- | --- | --- |
| `FR-101` | MOD-18、API-04 | 恰好 1 个 `.c` 输入 |
| `FR-102` | MOD-18 | `-o` 与默认 `a.s` |
| `FR-103` | API-05、§5.3 | 三个 dump 的唯一生成者 |
| `FR-104` | MOD-18 | `-h`/`--version` |
| `FR-105` | §5.4 退出码映射表 |  |
| `FR-106` | DS-14、§6.3 原子写、FL-01 步骤⑩ | 失败路径不落盘是全局不变量（§9.3-1） |
| `FR-107` | DD-06、DS-07 指纹、§6.3 产物顺序确定性 | 排序输出 + 无随机源 |
| `FR-108` | MOD-06 `Reporter`（错误计数上限 20） | 语义恢复点由 `FR-309` 支撑 |
| `FR-109`/`FR-112`/`FR-113` | MOD-07 `ProfileLoader`、API-21、FL-06、DC-03 | 兼容别名映射为 `disable` 列表项 |
| `FR-110` | **未设计 → 列为** `LW-08`**（P2，**`--stats` **的输出已由 §5.3 定义，缺的是与** `NFR-107` **的衔接说明）** | 见附录 LW 补充表 |
| `FR-111`/`FR-1001`/`FR-1002` | DS-07、SRS `IF-06`/`§6.9` 内置表 | 内置 profile 为代码常量，不落盘 |
| `FR-114` | FL-01 步骤②③、API-23 | 必须在任何源码解析之前 |
| `FR-115` | API-05 `dump_isa`、MOD-08 | 含被禁项与替代路径 |
| `FR-116` | API-05 `dump_isa_whitelist`、DS-07 `whitelist` | 输出行数受 `FR-116` 判据约束；别名问题见 DC-02/DD-09 |
| `FR-117`/`FR-521` | DS-08 `LoweringChoice.rejected`、MOD-05 | 被否决规则 + 原因文本 |
| `FR-118` | DD-06、§8 `NFR-107`/`NFR-108` | 模块载入期预解析 |
| `FR-119` | MOD-10 `app.py`、FL-05 | 无参数时仍为用法错误（64） |
| `FR-201`~`FR-210` | MOD-01、DS-01/DS-02、API-11 | 词法不感知 profile（SRS §4 注） |
| `FR-301`~`FR-311` | MOD-02、DS-03、API-12 | 递归下降 + 优先级爬升；14 级表见附录 A.4 |
| `FR-312`/`FR-313`/`FR-314` | **显式不做（Deferred）**：对应 SRS `§9.2` 的 `?:`/`switch`/`do-while`，本轮不设计；词法器已将其列为保留关键字并走 `FR-409` 的统一诊断模板 | 显式不做也是设计结论 |
| `FR-401`~`FR-415` | MOD-04、DS-04、API-13、§2.2 硬规则 2 | 三级作用域；**不 import** `isa`（`FR-415`） |
| `FR-501`~`FR-509`、`FR-513`~`FR-516` | MOD-05 `FrameLayout`/`Linearizer`/`Emitter` | 栈式生成、`s0` 帧指针、指针算术按 4 缩放 |
| `FR-510` | MOD-05 `LOWERING_TABLE[MUL/DIV/REM]`、MOD-11 软件三件套 | 两条路径行为一致由 `D-11` + B7 保证 |
| `FR-511`/`FR-512` | `FR-511`→MOD-13 `lint.sh`＋DS-07 白名单；`FR-512`→EXT-01（gas `-mno-relax` 无警告）＋MOD-12 | v1.0 中二者并列于 MOD-13，已拆分 |
| `FR-515`/`FR-517`/`FR-518` | `LOWERING_TABLE` 的 `XOR`/`CONST32`/`SHIFT_VAR` 三族 | 守卫由选项名改为能力谓词 |
| `FR-519` | DD-01、DD-07 `check_no_option_branch.py` | 结构上不可能违反 + 静态检查兜底 |
| `FR-520` | DS-08（每个 AOp 至少一条 `guard=True` 兜底规则） | 遍历全部 profile 的测试见 `TV-03` |
| `FR-601`~`FR-607` | MOD-11 `runtime.s` | 条件汇编 + `D-11` 边界语义 |
| `FR-608`/`FR-611`/`FR-612` | MOD-12、FL-06 步骤④、DS-15 | `--defsym` 由同一 profile 派生 |
| `FR-609`/`FR-809` | MOD-13、DD-09、DC-02 | 白名单唯一来源 + 窄/宽敏感性负例 |
| `FR-610` | MOD-15 `compare.sh` | 对照 GCC `-march=rv32i` |
| `FR-614`/`FR-615` | MOD-14、EXT-03、FL-07 | 集合比对 + 新增变体零代码 |
| `FR-701`~`FR-705` | MOD-06 `API-03`、DD-03 | caret 列与 `col` 一致 |
| `FR-706` | API-02、DD-02、MOD-09（`MemoryCollector`） | core 不直接 `print` |
| `FR-707` | `errors.py` 的消息模板（四要素：选项/指令名/替代/建议） | `FM-13`~`FM-15` 共用 |
| `FR-708` | DS-06、DC-01 码表 | GUI 只消费字段，不解析文本 |
| `FR-801`~`FR-813` | MOD-16、MOD-17、§12 | 静态检查与一键脚本 |
| `FR-901`~`FR-909` | MOD-09、MOD-10、SRS `IF-08` 布局 | 面板/诊断表/汇编/Lowering 报告 |
| `FR-910`/`FR-912` | API-34、FL-04、EXT-06 | 参数列表；超时可终止；不残留 |
| `FR-911` | API-33（与 `API-05` 的分工见 §5.1） | `.s` 另存 / 纯文本诊断 / Markdown 表格 |
| `FR-913` | §9.1 `IceError` + 对话框 + 等价 CLI | 命令行必须可复现同一 ICE |
| `FR-914` | FL-05、`GuiUnavailableError` | 单行、无 Traceback、退出码 64 |
| `FR-915` | DS-13、DD-10 | 基线 + 差集；写入时机见 DS-13 |
| `FR-916` | §2.2 硬规则 1、MOD-16 `check_imports.py` | GUI 只用 `API-01`/`API-05` |
| `FR-917` | README 的 CLI 对应表 | 由 `AC-12` 第 4 项人工核对 |
| `FR-918` | MOD-10（>128 KiB 提示） | 与 `IF-02` 上限一致 |
| `FR-919` | MOD-09（逻辑层可编程驱动 `API-31`/`API-32`） | 不创建可见窗口 |
| `FR-920` | DD-04、MOD-16 `check_layering.py` | 逻辑层零控件类型 |
| `FR-1003` | DS-08 中 `DIV`/`REM` 的独立守卫（`rem` 缺失时走 `a-(a/b)*b`，需 `DIV` 或 `__divsi3`/`__mulsi3` 兜底） | 由 `LOWERING_TABLE` 的规则顺序表达 |
| `FR-1004` | DS-07 指纹、DD-06 | 同进程多次编译一致 |
| `FR-1005` | MOD-08（按 DC-05 修订后仅做 AOp 级影响统计） | 与 P2 的"源码级统计"区分 |

### 11.2 非功能需求 → 设计元素

| 需求组 | 设计元素 |
| --- | --- |
| `NFR-101`、`NFR-102`、`NFR-106`、`NFR-107`、`NFR-108` | §8 各自独立一行；MOD-05 载入期预解析表；§6.3 指纹缓存；MOD-17 并行矩阵 |
| `NFR-103` | §8「规模增长比」一行；度量口径见 `LW-03` |
| `NFR-104`**、**`NFR-105` | **尚未闭合 → 遗留项** `LW-01`**、**`LW-02`**（§8.1）** |
| `NFR-201`~`NFR-209` | §6.3 一致性策略（含产物顺序确定性）、§9.3 全局不变量、§8 各对应行、MOD-17 的矩阵与敏感性子项 |
| `NFR-301`、`NFR-302` | §8 两行；MOD-18 `--doctor`；FL-05；MOD-17 |
| `NFR-304`、`NFR-305` | §8 两行；§7.2（面板即数据 / 诊断表单表 + 双击跳转）；DS-07 的 `diff_vs_default` |
| `NFR-303`、`NFR-402`、`NFR-702` | 遗留项 `LW-05`、`LW-06`、`LW-07`（§8.1） |
| `NFR-310`、`NFR-311` | §7.3 量化目标；FL-04 的 30 s 超时；MOD-18 `--doctor`；README 的 `FR-917` 对应表 |
| `NFR-401`~`NFR-407` | §2.2 依赖规则；DD-02（§0/§3 已修正为"类型放 `core/types.py`"）；DD-04（逻辑/视图分层）；MOD-16 四件套；§8 各行 |
| `NFR-501`、`NFR-506`、`NFR-509` | §2.3 目录结构、`requirements.txt` 锁定、`--doctor` 的离线检查项、EXT-05 |
| `NFR-502`、`NFR-504` | §8 可移植性一行；MOD-12（小端显式指定） |
| `NFR-503` | §8「版本可复现」一行；MOD-18 的 `--version` 固定字段序 |
| `NFR-601`~`NFR-605` | EXT-06（参数列表、无 shell、不可编辑模板）、手写词法/语法（不 `eval`）、无网络调用 |
| `NFR-701`~`NFR-705` | §12 的验证节奏与矩阵预算（DC-04）；`NFR-704` 的 5 工作日时效与 MOD-14 绑定 |
| `NFR-703` | §8 `NFR-703` 行 + §1.2 DC-04 的预算表；MOD-17 的并行单位与产物复用 |
| `NFR-801`、`NFR-802`、`NFR-803`、`NFR-807`、`NFR-809` | §7（交互）、§8（性能与内存）、FL-03/FL-04/FL-05（线程与进程模型）、MOD-17（`importorskip` 守卫） |
| `NFR-804`、`NFR-806`、`NFR-808` | §12 TV-09 的手工清单机制；MOD-10（大文件提示） |

> **两条维护规则**：① 本表只声明 §8（含 §8.1）与 §12 实际给出设计应对的编号；② 新增任何 P0 需求时，若其 §8 落点为空，必须在 §8.1 登记 `LW-xx`，不得让它在本表中"看似有、实际无"。

### 11.3 约束 → 设计元素（横切）

| 约束 | 设计落点 | 可核对形式 |
| --- | --- | --- |
| `CN-01`/`CN-18` | `core`/`cli` 零第三方；`gui` 仅 PySide6 | MOD-16 `check_imports.py` + `NFR-501` 的集合等式 |
| `CN-02` | DS-07 不变量：恒含 MV-ISA、恒为 RV32IM 子集 | MOD-07 `Feasibility` + `FM-14` 负例 |
| `CN-13` | §2.2 硬规则 1 | `check_imports.py`（import 图 + stdout/stderr 写入）+ `check_layering.py`（Qt 对象） |
| `CN-14`/`CN-15`/`CN-16` | §6.3 单源与解耦策略 | MOD-16 + `check_isa_consistency.sh` + `FR-415` 逐字节诊断判据 |
| `CN-17` | §2.1 前端的"薄"与 GUI 不实现 CLI 之外的能力 | `FR-917` 对应表 + `AC-12` 第 4 项 |
| `CN-19` | `gui` 源码标注 PySide6 版本与许可；不打包分发 | 评审 + §2.3 交付形态 |

* * *

## §12 测试与验证考虑

设计结论必须"可被检查或验证"。本设计把验证手段分成十三类，并明确各自**验证的是哪一层设计**。
| ID | 验证手段 | 验证对象 | 承载需求 |
| --- | --- | --- | --- |
| **TV-01** | **单元测试（注入** `MemoryReporter`**，无 I/O）** | MOD-01~05、07 的内部逻辑；`DS-01`~`DS-11` 的字段约束 | `FR-801`、`NFR-404`、`AC-01` |
| **TV-02** | **端到端（qemu）** | FL-01 全链路 + MOD-11/12 的目标集成 | `FR-802`、`AC-02`、`AC-04` |
| **TV-03** | **profile 矩阵不变性（9 profile × 6 程序）** | `LOWERING_TABLE` 的每条规则都被"走过"（`PF-02`/`PF-03` 专门覆盖降级路径） | `FR-808`、`AC-09`、`NFR-208`、`RS-17` |
| **TV-04** | **profile 敏感性（lint 窄/宽负例）** | 证明 `lint.sh` 确由 profile 驱动而非硬编码 | `FR-809`、`NFR-209`、`AC-03` 第③项 |
| **TV-05** | **静态检查（四件套）** | §2.2 的三条硬规则（含 DAG 无环）、`FR-519`、`FR-920` | `FR-810`、`FR-812`、`AC-12`、`AC-13` 第 2 项、`NFR-401` |
| **TV-06** | **offscreen GUI 往返（逐字节比对）** | MOD-09 逻辑层 + `API-31`~`API-33`；`AC-11` 三项 | `FR-907`、`FR-908`、`FR-919`、`FR-920`、`AC-11`、`AC-13` |
| **TV-07** | **故障注入（**`FM-01`**~`FM-21` 各至少一例）** | §9 的处理路径与恢复策略；退出码与 stderr 形态 | `FR-807`、`AC-06` |
| **TV-08** | **覆盖率门槛（**`check.sh` **内断言，E1/E2）** | §2 的分层是否真的带来可测性 | `NFR-403`、`AC-07` |
| **TV-09** | **手工清单（10 项，含像素级外观与平台适配）** | 视图层的外观与交互（明确不做自动断言的部分） | `NFR-806`、`NFR-804`、`NFR-505` |
| **TV-10** | **环境矩阵（E1/E2/E3，各自独立计时）** | FL-05 的降级路径、`AC-12` 的 P0 项、MOD-17 的 `importorskip` 行为 | `NFR-807`、`AC-12`、`AC-08`、`NFR-703` |
| **TV-11** | **性能与资源度量（5 次中位数）** | §8 中所有带阈值的项；触发条件含"换机/换 Python 版本/换 PySide6 版本即重测基线"（`NFR-702`） | `NFR-101`、`NFR-102`、`NFR-103`、`NFR-106`、`NFR-107`、`NFR-108`、`NFR-310`、`NFR-801`、`NFR-809` |
| **TV-12** | **一致性比对（profile vs** `hw_caps.json`**）** | FL-06 的"四处同源" | `FR-614`、`AC-10` |
| **TV-13** | **文档一致性核对（人工，评审期）** | §5.2 命名一致性规则、§11 对 §8 的声明是否与正文一致、编号唯一性 | 设计文档自身的"可验证性与规范性" |

**TV ↔ SRS** `TC` **组的衔接**（便于直接落到测试用例编写）
| TV | SRS `TC` 组 | 主要落点 |
| --- | --- | --- |
| TV-01 | `TC-1xx`~`TC-5xx` | MOD-01~05、MOD-07 |
| TV-02 | `TC-6xx` | FL-01、MOD-11/12 |
| TV-03 | `TC-1001`~`TC-1005`、`TC-5xx` | MOD-05 `LOWERING_TABLE` |
| TV-04 | `TC-809`、`TC-511` | MOD-13 |
| TV-05 | `TC-810`~`TC-812`、`TC-920`、`TC-941`~`TC-947` | MOD-16 |
| TV-06 | `TC-907`、`TC-908`、`TC-919`、`TC-920` | MOD-09 |
| TV-07 | `TC-701`~`TC-721` | §9 全表 |
| TV-08 | `TC-941`~`TC-947` | §2、§8 |
| TV-09 | `TC-971`~`TC-979`、README 手工清单 | MOD-10 |
| TV-10 | `TC-951`~`TC-953`、`TC-717` | FL-05、MOD-17 |
| TV-11 | `TC-901`~`TC-931` | §8 |
| TV-12 | `TC-614`、`TC-615` | MOD-14 |
| TV-13 | 评审记录 | 本文档 |

**设计的可验证性自检（三条设计原则）**

1.  **凡"逐字节相同"的判据，必须存在唯一生成函数** —— 否则不可自动断言。见于 `DD-03`（诊断）、`DD-11`（dump 文本）、`DS-14`（汇编）。
    
2.  **凡"不得出现 X"的约束，必须落到脚本**（`DD-07`） —— 否则约束只在文档里存在。见于 `FR-519`、`FR-810`、`FR-812`、`FR-920`、`NFR-401`（DAG）。
    
3.  **凡"跨 profile 行为一致"的性质，必须由构造保证而非由测试穷举** —— 穷举不可行（`NG-10`/`RS-12`），因此把"差异"全部收敛到 lowering 表的 `expand` 字段，使"一致性"成为**只有一处可能出错**的性质。见于 `DD-01`、`DD-06`。
    

**验证与实现顺序的对应**（`check.sh` 阶段 → 设计层）：静态检查（§2.2）→ 单元（§3）→ 端到端（§4.1）→ 矩阵（§10 DD-01）→ 一致性（§4.6）→ lint（§5 EXT-01/DC-02）→ 对照（§4.1）→ 覆盖率（§8）→ offscreen GUI（§7.2）。

* * *

## 附录 LW 补充表（`LW-08`）

| ID | 需求 | 优先级 | 说明 |
| --- | --- | --- | --- |
| `LW-08` | `FR-110`（`--stats`） | P2 | §5.3 已定义其 stderr 输出结构（`阶段名\t毫秒`），但未说明它与 `NFR-107`（profile 阶段 ≤5 ms）的度量如何共用同一打点；补一句即可闭合 |

* * *

## 附：文档结束语与交付物对应

| 本次实验要求的提交物 | 本文对应 |
| --- | --- |
| 设计文档（覆盖 12 个设计要素） | §2 ~ §12（索引见 §0） |
| 需求基线说明 | §1.1（沿用 SRS-MYCC-001 v1.2，以编号引用，给出承接章节对照） |
| 需求变更说明 | §1.2（`DC-01`~`DC-06`，每项含缺陷/改动/影响的需求编号） |

引用关系说明：本文所有对需求的引用均指向 SRS-MYCC-001 v1.2 的原文编号，其中 SRS `IF-06(d)` 的抽象操作×降级路径对照表被直接采纳为 `LOWERING_TABLE` 的数据来源，SRS `IF-08` 的窗口线框被直接采纳为工作台布局规范，SRS `§7` 的 `FM-01`~`FM-21` 被直接采纳为异常处理设计清单；本设计未虚构任何第三方能力或参数，`EXT-01`~`EXT-06` 的每一项均对应 SRS `§3.3` 的 `DP-01`~`DP-09`或`IF-0x` 接口。