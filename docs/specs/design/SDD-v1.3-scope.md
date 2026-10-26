# SDD-MYCC-001 v1.3 — 编译器范围收敛修订

日期：2026-10-26　版本：mycc 0.3.0　变更单：**CR-SCOPE-001**。

对应 SRS v1.4 和 [范围说明](../../guides/scope.md)。旧设计 v1.1/v1.2 保留；本修订覆盖默认入口、模块职责和主界面设计。CPU21 的执行协议继续有效，归属变为外部适配。

## DD-20：编译核心保持通用，适配显式注入

核心仍为原七模块，不导入 `adapters`、GUI、CLI 或外部工具。移出固定 MMIO 类、板卡能力检查与 VGA 内置函数；core/isa 中仅保留 cpu21 参考指令集合这一份数据。

`CodegenPolicy` 是叶子模块中的通用结构，字段包括全局 BSS 初始化策略、初始化符号、低地址重定位范围和可选栈边界/陷阱符号。默认策略 generic 不启用这些外部约定。`CompileOptions.externals` 用于适配层注入外部函数签名；语义分析不直接认识 VGA。

core.compile 校验 options.target 与注入 policy.name 一致，避免只传板卡名就悄悄启用硬件逻辑。默认 profile 为 PF-01。ISA lowering 继续按能力守卫，地址/初始化等可选机制按策略字段处理，codegen 中不出现 CPU21 特判。

## DD-21：外部适配目录

```text
adapters/
  __init__.py          显式目标检查和编译选项工厂
  cpu21/
    __init__.py        CPU21 策略/外部函数注入和 compile 包装
    config.py          固定硬件事实与 MMIO 校验
    assets.py          启动模板处理、ROM 格式导出
    runtime/           启动与 VGA 控制台
    linker.ld          板卡最终地址布局
    board.json/isa.json
  generic/             旧通用裸机启动/链接样例及占位 MMIO
  qemu/                Linux-user 启动与链接样例
runtime/               通用软件算术/内存辅助及 I/O 格式函数
```

`tools.build`、lint、compare、verify_cpu21 是外部编排工具。只有显式 CPU21 目标才加载该适配，普通 CLI 编译不导入 adapters。无工具链仍可正常完成 C → .s。

兼容入口 `mycc --target cpu21` 由 CLI 加载适配，完成验证后向 core 注入策略；Python 调用采用 `adapters.cpu21.compile` 或 options 工厂。旧 `core.CPU21Board/check_target` 改为适配层接口，迁移位置在文档中明确列出。

## DD-22：工作台只组织编译

WorkbenchState 默认 PF-01，示例为 square 函数和 main 返回值；build_request 统一产生 generic 编译请求。全部合法 ISA 预设和组可选，cpu21 显示为硬件参考 ISA。

视图保留文件操作、编译/取消、汇编/Token/AST/IR/Lowering、导出及诊断跳转。移除 QProcess、运行/构建/lint 工具栏、输出进程标签和 MMIO 控件。帮助菜单仅展示可选外部命令，不执行它们。编译依然走 worker，视图更新在主线程。

持久化格式为 schema_version=2；只保存基线、差集和 legacy 通用数据。旧 board 字段原样转存 legacy，提示用户；不把它注入编译器，不因旧硬件配置重置合法 ISA。

## DD-23：验收与证据分层

核心演示固定为 compiler_demo、ISA lowering 差异和诊断恢复。普通检查执行既有测试/覆盖率/汇编矩阵，不要求运行外部板卡。`check --cpu21` 为显式集成回归，在软件目录内编译原始 RTL 并验证生产固件。

0.2.0 的 16 组执行报告保留。0.3.0 新增 compiler_demo 的有/无 mul 两组执行，独立记录结果与外部源文件哈希。物理上板、QEMU/GCC 及未测性能仍按各自证据报告。

| 要求 | 设计 | 测试 |
|---|---|---|
| SC-CORE-01/02/03 | 通用 core、GNU 输出与能力表 | tests/test_scope.py、compiler_demo |
| AC-16 | DD-20/22 | 新进程不导入 adapters、GUI 无进程/地址、AST 层次检查 |
| AC-17 | DD-21/23 | 显式 CPU21 构建、18 组正式固件执行和哈希 |
| FR-915 | DD-22 | 旧 board 迁移、schema 版本及设置往返 |
