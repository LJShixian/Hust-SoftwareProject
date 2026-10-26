# CPU21 外部适配示例

此目录承接 mycc 0.2.0 的板卡适配。主编译器默认输出 GNU 汇编，不加载本适配；GUI 中选择 cpu21 参考 ISA 也不会加载本目录的策略。

显式使用：

```powershell
# 适配后的汇编（包含 BSS 初始化入口、板卡栈保护等）
python -m mycc examples/compiler/arrays.c --target cpu21 -o build/arrays-cpu21.s

# 完整固件，全部输出留在软件目录
python -m tools.build examples/compiler/arrays.c --target cpu21 --board-file adapters/cpu21/board.json -o build/arrays

# 可选：只读使用外部 RTL 验证
python -m tools.verify_cpu21 --root D:\Xilinx\Project\risc-v
```

目录职责：

| 文件 | 内容 |
|---|---|
| `__init__.py` | 硬件 ISA 校验、编译策略和运行时外部函数注入 |
| `config.py` / `board.json` | 实际 MMIO、地址校验和硬件约束 |
| `runtime/start.s` | 栈/BSS/显存初始化、中断关闭、VGA 底层及退出 |
| `runtime/console.c` | 字形转换、换行和控制台状态 |
| `linker.ld` | Harvard ROM 32 KiB、RAM 4 KiB 和容量断言 |
| `assets.py` | 无 lui 启动寻址及 32 位 ROM 导出 |
| `isa.json` | 编译器可使用的 32 指令参考集合 |

核心仅消费通用 `CodegenPolicy`：全局初始化方式、低地址重定位范围和可选栈检查。固定地址、容量、字形及故障状态都由本适配提供。Python 接口为 `adapters.cpu21.compile(src, profile=None)`；直接给 core 传 target 名不会自动加载板卡代码。

硬件限制仍然有效：没有 UART；VGA 小写转大写，0/O、9/Q 共用字形；退出写 LED/SEG；默认不接管 ISR。普通 generic 汇编不能直接当作该 Harvard 目标的完整固件。完整扫雷继续由原有 GCC 流程构建。

产物为本地 ELF/BIN、8192 个 32 位字的 HEX、VH、Logisim 文件及 manifest。不写入 FPGA 项目，不生成或下载 bitstream。0.2.0 的历史验收证据在 `docs/verification/`；0.3.0 需单独运行回归。
