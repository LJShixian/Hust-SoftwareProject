# Logisim 课堂 CPU 适配

面向《硬件综合训练》课程里自己搭的 Logisim 单周期/流水 RISC-V CPU。目标是课堂现场：写一段 C，一条命令拿到 hex，拖进 Logisim 直接跑。
> **电路侧怎么改？** 本文只讲编译器和镜像。让 CPU 真正支持标准系统调用（`a7=10/11/12`）
> 的接法写在 **[HARDWARE-REUSE.md](HARDWARE-REUSE.md)**，思路是复用你现有的 `ecall` 输出电路：
> 改一个常量 + 拆一个反相器（停机条件）、给 TTY 接 Write Enable（输出）、加键盘 + 三个选择器（输入）。
> 现成的 DP 演示程序见 `examples/logisim/knapsack.c`。
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
| ECALL | **标准 RISC-V 系统调用约定**：`a7` 选服务号，参数与返回值都在 `a0`。`11`=打印一个字符、`12`=读一个字符、`10`=退出。前两者执行完继续跑，只有 `10` 才停机等 `go` | RISC-V / RARS 通行的 syscall 编号；电路侧怎么接见 [HARDWARE-REUSE.md](HARDWARE-REUSE.md) |

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

`--target logisim` 已隐含 `--rars` 与 `--logisim`。现有 11 个示例编出来是 **319~964 字**（上限 1024）。

运行时是按需内联的：`printint`/`printhex`/`printstr`（`runtime/io.c`，建在 `putchar` 上）
和 `readint`/`readchar`（`runtime/input.c`，建在 `getchar` 上）都是普通 C 函数，只保留镜像里
真正引用到的那些。所以一个只打印的程序不带 `getchar` 依赖。

## 现成的课堂演示程序

`examples/logisim/demo.c`：全局数组 + 指针遍历 + 软件乘除 + 移位异或。
因为现在有真正的字符输出，结果不再是数码管上的一串十六进制，而是终端上看得懂的文本：

| # | 输出 | 含义 |
|---|---|---|
| 1 | `scores[0] = 7` | 全局数组初值已装入 RAM |
| 2 | `sum      = 33` | 指针遍历 + 循环累加 |
| 3 | `max      = 9` | 逐元素比较 |
| 4 | `sum*2    = 66` | 软件乘法（这台 CPU 没有 M 扩展） |
| 5 | `sum/4    = 8` | 软件除法（32 位恢复余数） |
| 6 | `sum<<2   = 132` | 用到 **SLL** |
| 7 | `sum^0x5a = 123` | 用到 **XOR** |

ROM 771 字、RAM 52 字（208 字节，装那些标签数组）。

`examples/logisim/demo_pause.c` 是同一个程序的**分段停钟版**：每段后面多一行 `exit(0)`，
于是每按一下 `go` 只跑一段，方便课上边讲边放。两个版本的差别就是这一行：

```c
show("sum", sum);  exit(0);   /* 这一段跑完就停钟，讲完再按 go */
show("sum", sum);             /* 打印完直接往下跑 */
```

### 展示编译器：0/1 背包

`examples/logisim/knapsack.c`（洛谷 P1048「采药」同型）是一段真正带输入输出的 DP 程序，
用来展示编译器处理非平凡代码的能力：

```c
int cost[16]; int worth[16]; int best[81];

int imax(int a, int b) { if (a > b) return a; return b; }

int main(void) {
    int cap; int count; int i; int w;
    scanf("%d %d", &cap, &count);
    i = 0;
    while (i < count) { scanf("%d %d", &cost[i], &worth[i]); i = i + 1; }
    ...
    i = 0;
    while (i < count) {
        w = cap;
        while (w >= cost[i]) {          /* 逆序扫容量，0/1 背包的关键 */
            best[w] = imax(best[w], best[w - cost[i]] + worth[i]);
            w = w - 1;
        }
        i = i + 1;
    }
    printf("max value for cap %d = %d\n", cap, best[cap]);
    return 0;
}
```

样例输入 `70 3 / 71 100 / 69 1 / 1 2`，输出：

```
items: (71,100) (69,1) (1,2)
max value for cap 70 = 3
```

ROM 964 字、RAM 165 字（660 字节）。容量与株数上限受 1024 字节 RAM 限制，取 `cap <= 80`、`count <= 16`。

## 四个只为这台机器存在的决定

1. **I/O 走标准系统调用，不停机也能输出。** `a7=11` 打印一个字符、`a7=12` 读一个字符，两者执行完都继续跑；只有 `a7=10`（`exit`）才停机等 `go`。`printint` / `printhex` 不是系统调用，而是 `runtime/io.c` 里用 `putchar` 写的普通 C 函数，格式化十进制/十六进制是软件的事。入口存根的 `addi a7,zero,10; ecall` 是程序末的停机点。同一份 `.asm` 丢进 RARS 跑出来完全一致。

2. **`sp` 由入口存根装载。** 真实硬件上电后寄存器全为 0，而 RARS 会替你把 `sp` 设成 `0x7fffeffc`。不装载就一进函数写到 `0xFFFFFFF0`。默认 `sp=1024`（RAM 顶端，向下增长），可用 `--stack-top` 改。

3. **全局变量地址只做有界重定位。** 没有 `lui` 时，编译器原本会走"PC 相对常量池"（`jal` 取 PC + `lw 8(rd)` 读常量）。这条路在 Harvard 上永远不成立：`lw` 读不到 ROM。因此适配器设 `data_address_bits=10`，改用 `addi rd,zero,%lo(sym)` + `slli`/`srli` 掩码到 10 位，地址直接落在 0..1023。

4. **`.word` 必须离开 `.text`。** `switch` 的跳转表被编译器内联在文本段里。RARS 直接报错，硬件上更糟：表在 ROM 里，`lw` 取不到。`--rars` 会把数据指令搬进 `.data`，标签随之一并搬迁。

## 验证方式

| 验证 | 方法 | 当前结果 |
|---|---|---|
| 编码正确性 | 把 `--rars` 单文件交给真 RARS 汇编并 `dump .text HexText`，与内置编码器逐字比对 | 10 程序 × 3 指令集 = **30/30 完全一致** |
| 行为正确性 | 同程序分别按 Logisim 指令集（走全部软件回退）与 PF-01 编译 ，在 RARS 里跑，标准输出必须相同 | **10/10 一致** |
| 镜像合规性 | 把 `.rom.hex` 反汇编回来，检查助记符与容量 | 10 程序 **0 问题** |

复跑：`python -m tools.check_logisim`（零依赖）与 `python -m tools.check_rars`（需 Java，缺失自动跳过）。

RARS 命令行有个坑：`mc CompactDataAtZero` **必须写在 `a` 之前**，否则被忽略，数据段仍停在 `0x10010000`，`%hi` 就对不上了。

## 边界

- **想看到输出就调用 `putchar` / `printint` / `printhex`，**它们全部落到 `a7=11` 的字符输出上。硬件侧需要一个 TTY（以及 `a7=12` 读键盘时的一个 Keyboard）；接线步骤见 [HARDWARE-REUSE.md](HARDWARE-REUSE.md)。
- **`a7` 服务号只有 10/11/12 三个。** 这里没有 `print_string`、没有文件、没有 `sbrk`：字符串打印用 `while(*p) putchar(*p++);` 在 C 里写就行。
- **RAM 只有 1024 字节。** 全局变量从 0 往上，栈从 1024 往下，两者不能相遇。
- **ROM 上限 1024 字。** 现有 10 个示例编出来是 319~810 字。
- 这是**行为级**验证：证明指令序列与 ISA、寻址、退出约定一致，不覆盖时序、时钟与板级电平。真正的"拖进 ROM 第一拍取指是否正确"需要在 Logisim 里确认。
