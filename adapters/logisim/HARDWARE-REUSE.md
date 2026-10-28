# 硬件改造：复用你现有的 `ecall` 输出电路

你原来的输出逻辑就三块：**比 `0x22` → 反相 → 与 `ecall`（得到停机信号）**，加上
**`MemToReg` 三选一 → 32 位寄存器 → `LedData` 数码管**。标准系统调用要的东西几乎一样，
所以**不用重搭，改几个常量、加一个键盘就够**。

改动一共 **3 处**，全在 `◆软件工程演示` 页顶层。`◆Regifile` 是共享子电路，**不要进去改**。

---

## 软件发什么

| `a7` | 服务 | 说明 |
|---|---|---|
| `11` | `putchar` | `a0` 低 7 位是字符，打完**继续跑** |
| `12` | `getchar` | 从键盘取一个字符**写回 `a0`**，继续跑 |
| `10` | `exit` | 停机等 `go` |

编译器生成的存根就三行：

```asm
putchar:              getchar:              exit:
addi a7,zero,11       addi a7,zero,12       addi a7,zero,10
ecall                 ecall                 ecall
jalr zero,0(ra)       jalr zero,0(ra)       jalr zero,0(ra)
```

关键点：**调用 `putchar` 之前，编译器已经把字符放进 `a0` 了**。所以你要锁存的那个值
就在 `a0` 里——和你原来锁存 `a0` 上数码管是同一个数据源，一点都不用改。

---

## 改动 1：停机条件 —— 改一个常量、拆一个反相器

现在这条链是：

```
Constant 0x22 @(1160,850) ─→ Comparator @(1240,840)
                                     ↓ (相等)
                              NOT Gate @(1140,430)
                                     ↓
                    AND Gate @(1500,830)  ←┐
                    Tunnel halt @(1550,830) ┘
```

`NOT(a7==0x22)` 就是"不是 34 就停"，这是旧约定。标准约定是"**是 10 才停**"：

| 动作 | 元件 |
|---|---|
| 常量值 `0x22` → `0xa` | `Constant @(1160,850)`，双击改值 |
| **删掉反相器** | `NOT Gate @(1140,430)` |
| 比较器的 `=` 输出直接连到原来反相器的**输出**端 | `Comparator @(1240,840)` → `AND Gate @(1500,830)` |
| 顺手删掉私有扩展残留 | `Constant 0x23 @(1160,1050)` + `Comparator @(1240,1040)`；`Constant 0x24 @(1160,1110)` + `Comparator @(1240,1100)` |

改完：`halt = ecall AND (a7 == 10)`。打印、读键盘之后都继续跑，只有 `exit` 停钟等 `go`。

> 那两对 35/36 的比较器是之前做到一半的私有扩展，标准 ABI 用不上，输出线本来也没接出去。

---

## 改动 2：TTY 输出 —— 复用那个 32 位寄存器

你现在的显示路径是：

```
RDin ─┐
      ├→ Multiplexer(select=2) @(1640,610) → Tunnel RDin @(1660,610)
PC+4 ─┘      ↑ MemToReg

ALUresult → Register(32) @(1440,960) → Tunnel LedData @(1490,960) → 数码管
                ↑ CLK @(1420,1000)
```

这个寄存器就是"锁存 `a0`"。**它现成的，只要多引一条线到 TTY。**

### 2.1 从寄存器输出分出低 7 位

在 `LedData @(1490,960)` 那根线上加一个 **`Splitter`**：

- `Fan Out = 2`，`Bit Width In = 32`
- `Bit 0..6 → 0`（引出组 0），`Bit 7..31 → 1`（引出组 1）

组 0 那根 **7 位线** → TTY 的 `D`（西边上面引脚）。组 1 不用接。

TTY 的 `Char bit width` 属性已经是 `7`，和这根线对得上，不用改。

### 2.2 接 TTY 剩下的两个脚

你这个 `Register @(1440,960)` 只接了数据和时钟、没有使能脚，说明它**每拍都在锁存**。
直接接 TTY 会一直重复打印同一个字符，所以要过滤。**TTY 自带 `Write Enable`，正好用：**

| TTY 引脚 | 接什么 |
|---|---|
| Data（西上） | 2.1 的 `Splitter` 组 0（7 位） |
| Clock（西下三角） | `CLK` 隧道（页里已有） |
| **Write Enable**（南边左 1） | **`ecall AND (a7==11)`** |
| Clear（南边左 2） | `Constant` 1 位 = `0` |

`Write Enable = 0` 时 TTY 完全忽略时钟，所以只有真正 `putchar` 的那一拍写一次。

**`ecall AND (a7==11)` 怎么来：** 复制改动 1 里的
`Comparator @(1240,840)` 那一对，常量改成 `0xb`，然后用页里现成的 2 输入 `AND Gate`
把它和 `Tunnel ecall @(670,500)` 相与。

---

## 改动 3：键盘输入（`a7=12`）

### 3.1 加键盘

放一个 `Keyboard`（输入/输出库）：`Char bit width = 7`、`Buffer Length ≥ 16`。

| Keyboard 引脚 | 接什么 |
|---|---|
| Clock（西边三角） | `CLK` |
| Read Enable（南边左 1） | **`ecall AND (a7==12)`** |
| Clear（南边左 2） | `Constant` 1 位 = `0` |
| Data（南边最右，7 位） | 一个 `Bit Extender`（7 → 32，Zero 扩展） |

### 3.2 把字符写回 `a0`

`ecall` 时 `RegWrite` 是 0、`W#` 是 0，所以要从旁边插一脚。在寄存器堆三个输入端各加一个
选择器（**全部在顶层，不要进 `◆Regifile`**）：

| 插在哪 | 元件 | `sel = ecall AND (a7==12)` 时 |
|---|---|---|
| `◆Regifile` 的 `Din`（32 位写数据） | 32 位 2 选 1 `Multiplexer` | `1` → 键盘值，`0` → 原来的 `RDin` |
| `◆Regifile` 的 `W#`（5 位写地址） | 5 位 2 选 1 `Multiplexer` | `1` → `Constant` 5 位 = `0xa`（即 `x10`），`0` → 原来的 `IR[11:7]` |
| `◆Regifile` 的 `WE`（1 位写使能） | 1 位 `OR Gate` | `WE' = RegWrite OR (ecall AND (a7==12))` |

于是 `a7=12` 的 `ecall` 那一拍，硬件给 `x10` 写了一次键盘字符——这正是标准 ABI 里
"返回值放在 `a0`" 的意思。其它时刻三个选择器都走原来的路，行为完全不变。

---

## 自检清单

先用最小程序验证输出，再接键盘。

```powershell
# 34 字的最小自检：只打 "A" 和换行
python -m mycc build/demo/mini.c --target logisim -o build/demo/mini.asm

# 完整一点：Hi / 42 / 0x80000000
python -m mycc examples/compiler/hello.c --target logisim -o build/demo/hello.asm
```

把 `.rom.hex` 装进 ROM（`v2.0 raw`，每行一个 32 位字），复位跑。

| # | 看什么 | 期望 |
|---|---|---|
| 1 | 复位后 | TTY 空白，数码管是 0 |
| 2 | 跑到第一个 `a7=11` | TTY 出现 `A`，**CPU 不停**，继续跑 |
| 3 | `mini` 跑完 | TTY 显示 `A` 然后换行，停在 `a7=10` |
| 4 | `hello` 跑完 | TTY 显示 `Hi` / `42` / `0x80000000` |
| 5 | 按 `go` | 从停点继续（走到入口存根末尾的 `jalr`，属正常） |
| 6 | 键盘 | 先 poke 键盘打 `A`，跑到 `a7=12` 后 `a0` 应为 `0x41` |

---

## 常见故障

| 现象 | 原因 |
|---|---|
| TTY 刷满同一个字符 | `Write Enable` 接成了 1，或接了裸 `ecall` 没和 `a7==11` 相与 |
| TTY 打出乱码 | `Splitter` 位段选错（应取 `Bit 0..6`） |
| 打出一个字符就停 | 改动 1 的常量没改成 `0xa`，或反相器没拆 |
| 程序完全不跑 | `Comparator @(1240,840)` 的 `=` 输出接到了反相器的**输入**端，应接输出端 |
| `getchar` 永远返回 0 | 键盘没拿到焦点（要先用 poke 工具点一下再打字） |
| `getchar` 一次吃掉两个 | `Read Enable` 接了裸 `ecall`，没和 `a7==12` 相与 |
| 一跑就飞 | `W#` 的选择器位宽设成 32 了（必须 5 位） |
| 其它电路（流水线、中断版）坏了 | 进了 `◆Regifile` 子电路内部改东西 |

改完 `Ctrl+S` 保存 `.circ`。**改之前先另存一份备份。**
