# QEMU 外部验证适配

`python -m tools.build examples/compiler/compiler_demo.c --qemu` 使用这里的 Linux-user 启动和链接布局，配合外部 `qemu-riscv32` 执行。Linux 系统调用只存在于此验证适配，不属于 FPGA 指令要求。

本机未安装 qemu-riscv32，不能把汇编/链接成功当作运行通过。可使用明确选择的 CPU21 RTL 集成验证路径检查编译器示例；普通源码编辑、ISA 配置和汇编生成均无需 QEMU。
