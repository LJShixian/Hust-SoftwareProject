# 通用裸机集成样例

这是可选外部构建样例，不是任意 RISC-V 板卡的保证可用配置。它提供示例启动、统一可读代码/数据地址空间假设、链接布局及占位 MMIO。

`python -m tools.build file.c --target generic` 会生成该样例的固件。实际使用前，外部集成者必须确认启动、数据初始化、RAM/栈、UART 和显示协议。mycc 的普通 `C → .s` 编译不依赖这些内容。

需要 CPU21 时应显式使用 `--target cpu21`；需要 Linux-user QEMU 时使用 `--qemu`。
