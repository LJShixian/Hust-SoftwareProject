# Logisim 课堂 CPU 适配

面向《硬件综合训练》课程里自己搭的 Logisim 单周期/流水 RISC-V CPU。目标是课堂现场：写一段 C，一条命令拿到 hex，拖进 Logisim 直接跑。

## 指令集（依据：设计报告表 1.1）

权威来源是课程设计报告表 1.1 及其下方补充说明，不是从测试程序推断的。

**表 1.1 的 28 条**（1~24 为任务书基本指令，25~28 为学号 1453 的 CCAB 差异化指令）：

| # | 助记符 | 类型 | # | 助记符 | 类型 |
|---|---|---|---|---|---|
| 1 | ADD | R | 15 | BNE | B |
| 2 | ADDI | I | 16 | SLT | R |
| 3 | AND | R | 17 | SLTI | I |
| 4 | ANDI | I | 18 | SLTU | R |
| 5 | SLLI | I | 19 | JAL | J |
| 6 | SRAI | I | 20 | JALR | I |
| 7 | SRLI | I | 21 | ECALL | I |
| 8 | SUB | R | 22 | CSRRSI | I |
| 9 | OR | R | 23 | CSRCI | I |
| 10 | ORI | I | 24 | URET | I |
| 11 | XORI | I | 25 | SLL | R |
| 12 | LW | I | 26 | XOR | R |
| 13 | SW | S | 27 | SB | S |
| 14 | BEQ | B | 28 | BLTU | B |

**Logisim 版额外支持**：`CSRRW`、`DIVU`、`REMU`（表注：还额外支持 URET/CSRRSI/CSRRCI/CSRRW 四条中断相关指令与 DIVU/REMU 两条除法指令）。

**明确不支持**：`LUI`、`SLTIU`、`M` 扩展乘除法、`LB/LBU/LH/LHU/SH`、`BGE/BGEU/BLT`、`AUIPC` ——这些是 **Vivado 版**才补齐的。

合计 **31 条译码**（28 + CSRRW/DIVU/REMU）。其中 `ecall` 是陷阱，其余 30 条是可选能力；mycc 只需要其中 **24 条**（`--profile logisim` / `PF-08`），`DIVU/REMU/CSRRW/CSRRSI/CSRRCI/URET` 六条编译器从不生成。

## 硬约束

| 项目 | 值 | 来源 |
|---|---|---|
| 指令 ROM | 1024 字 × 32 位，**按字寻址** | `.circ` 中 `ROM addrWidth=10 dataWidth=32`；且基准程序 287 字、中断测试 344 字，字节寻址只有 256 字根本装不下 |
| 数据 RAM | 1024 字节，**字节寻址**、小端 | `MIPS RAM addrWidth=10`；`sb.txt` 中字节地址 0..31 再按字读回 |
| 结构 | Harvard：ROM 取指，RAM 读数 | `sw 0(x)` 不覆盖代码 |
| 链接器 | 无 | 单文件汇编 |
| ECALL | **a7=34：显示 a0 后继续；其它 a7：停机等 go** | 表 1.1 第 21 条备注；基准程序 37 条 ecall 中 32 条 a7=34、5 条 a7=10（停点）；在真实电路上实测确认 |

## 用法

```powershell
python -m mycc demo.c --target logisim -o build/demo/demo.asm
```

产物：

| 文件 | 用途 |
|---|---|
| `demo.asm` | 单文件汇编，可在 RARS（内存配置选 **compact, data at 0**）里直接运行 |
| `demo.rom.hex` | `v2.0 raw`，每行一个 32 位字，加载到 Logisim 的 ROM |
| `demo.ram.hex` | 仅当程序有初值全局变量时生成，加载到 RAM |

`--target logisim` 已隐含 `--rars` 与 `--logisim`。现有 9 个示例编出来是 **166~449 字**（上限 1024）。

## 现成的课堂演示程序

`examples/logisim/demo.c`：全局数组 + 指针遍历 + 软件乘除 + 移位异或，共 7 个 `printhex` 检查点。在 RARS 里跑验证过，依次输出：

| # | 显示值 | 含义 |
|---|---|---|
| 1 | `0x00000007` | `scores[0]`，全局数组初值已装入 RAM |
| 2 | `0x00000021` | 累加和 33（指针遍历 + 循环） |
| 3 | `0x00000009` | 最大值（逐元素比较） |
| 4 | `0x00000042` | 33×2 = 66，软件乘法（无 M 扩展） |
| 5 | `0x00000008` | 33/4 = 8，软件除法 |
| 6 | `0x00000084` | 33<<2 = 132，用到 **SLL** |
| 7 | `0x0000007b` | 33^0x5A = 123，用到 **XOR** |

ROM 452 字、RAM 6 字。这个版本在硬件上会把 7 个值连续显示完再停在结尾。

`examples/logisim/demo_pause.c` 是同一个程序的**逐值停顿版**：每个 `printhex` 后面多一行 `exit(0)`，于是每按一下 `go` 停在一个值上。课上演示用这个更合适（ROM 491 字）。

两个版本的关系就是这一行：

```c
printhex(sum);  exit(0);   /* 停在这里，看清 0x21 再按 go */
printhex(sum);             /* 显示完立刻继续 */
```

## 四个只为这台机器存在的决定

1. **停机是 a7 决定的，不是 ecall 本身。** `a7=34` 只把 a0 显示成十六进制然后继续执行；其它 a7 才停机等 `go`。课程基准程序 37 条 ecall 里 32 条是 a7=34 的显示、只有 5 条是 a7=10 的分段停点。图像路径的映射因此是：`printhex`/`printint` → `a7=34`（这台 CPU 只有十六进制显示），`putchar` → 空转（无字符显示设备），`exit` → `a7=10`——C 程序想停下来看一眼就调 `exit(0)`。入口存根的 `addi a7,zero,10; ecall` 是程序末的停机点。

2. **`sp` 由入口存根装载。** 真实硬件上电后寄存器全为 0，而 RARS 会替你把 `sp` 设成 `0x7fffeffc`。不装载就一进函数写到 `0xFFFFFFF0`。默认 `sp=1024`（RAM 顶端，向下增长），可用 `--stack-top` 改。

3. **全局变量地址只做有界重定位。** 没有 `lui` 时，编译器原本会走"PC 相对常量池"（`jal` 取 PC + `lw 8(rd)` 读常量）。这条路在 Harvard 上永远不成立：`lw` 读不到 ROM。因此适配器设 `data_address_bits=10`，改用 `addi rd,zero,%lo(sym)` + `slli`/`srli` 掩码到 10 位，地址直接落在 0..1023。

4. **`.word` 必须离开 `.text`。** `switch` 的跳转表被编译器内联在文本段里。RARS 直接报错，硬件上更糟：表在 ROM 里，`lw` 取不到。`--rars` 会把数据指令搬进 `.data`，标签随之一并搬迁。

## 验证方式

| 验证 | 方法 | 当前结果 |
|---|---|---|
| 编码正确性 | 把 `--rars` 单文件交给真 RARS 汇编并 `dump .text HexText`，与内置编码器逐字比对 | 9 程序 × 3 指令集 = **27/27 完全一致** |
| 行为正确性 | 同程序分别按 Logisim 指令集（走全部软件回退）与 PF-01 编译，在 RARS 里跑，标准输出必须相同 | **9/9 一致** |
| 镜像合规性 | 把 `.rom.hex` 反汇编回来，检查助记符与容量 | 9 程序 **0 问题** |

复跑：`python -m tools.check_logisim`（零依赖）与 `python -m tools.check_rars`（需 Java，缺失自动跳过）。

RARS 命令行有个坑：`mc CompactDataAtZero` **必须写在 `a` 之前**，否则被忽略，数据段仍停在 `0x10010000`，`%hi` 就对不上了。

## 边界

- **想看到输出就用 `printhex` 或 `printint`。** 这两个都映射到 `a7=34`，显示的是**十六进制**（这台 CPU 只有十六进制显示）。`putchar` 是空转：没有字符显示设备，而且每个分隔空格都停一下只会把真正的检查点埋掉。另一种办法是让程序把结果写进全局数组，直接看 Logisim 的 RAM。
- **RAM 只有 1024 字节。** 全局变量从 0 往上，栈从 1024 往下，两者不能相遇。
- **ROM 上限 1024 字。** 现有 9 个示例编出来是 166~449 字。
- 这是**行为级**验证：证明指令序列与 ISA、寻址、退出约定一致，不覆盖时序、时钟与板级电平。真正的"拖进 ROM 第一拍取指是否正确"需要在 Logisim 里确认。
