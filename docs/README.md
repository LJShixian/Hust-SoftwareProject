# 文档索引

先读根目录 [README](../README.md) 了解入口和流程，再按以下顺序阅读规范。

## 当前范围与规范

| 文档 | 用途 |
|---|---|
| [范围说明](guides/scope.md) | 当前产品边界及核心验收；先于程序修改提交 |
| [SRS v1.2](specs/requirements/SRS-v1.2.md) | 通用需求基线 |
| [SRS v1.4](specs/requirements/SRS-v1.4-scope.md) | 当前范围修订，覆盖默认行为和冲突项 |
| [SDD v1.1](specs/design/SDD-v1.1.md) | 编译器设计基线 |
| [SDD v1.3](specs/design/SDD-v1.3-scope.md) | 当前模块、适配注入和工作台设计 |
| [目录整理记录](guides/file-layout.md) | 路径迁移和验证留痕 |

修订是增量文件，需与基线一起阅读，冲突项以最新范围修订为准。迁移仅调整位置和导航，原文与历史版本继续保留在 Git 中。

## CPU21 外部适配

- [适配使用说明](../adapters/cpu21/README.md)：当前命令、资产和硬件限制。
- [SRS v1.3 CPU21 修订](specs/requirements/SRS-v1.3-cpu21.md)、[SDD v1.2 CPU21 修订](specs/design/SDD-v1.2-cpu21.md)：板卡专用约定；主流程职责以最新范围修订为准。

## 历史与留痕

| 文档 | 阶段 |
|---|---|
| [软件创意](history/project-ideas.md)、[决策纪要](history/decisions.md) | 初始设想和需求形成 |
| [SRS v1.0](specs/requirements/SRS-v1.0.md) | 早期需求 |
| [0.1.0 实施](history/0.1.0-initial.md)、[兼容审计](history/0.1.0-fpga-audit.md) | 最初实现及软硬件差异 |
| [0.2.0 CPU21 适配](history/0.2.0-cpu21.md) | 板卡适配实施与验收 |
| [0.3.0 范围收敛](history/0.3.0-scope.md) | 恢复以编译器为中心的实施记录 |

历史记录的命令、旧路径、数量与行为对应当时版本；当前命令以根 README 为准，迁移关系见目录整理记录。

## 证据与图片

- [0.2.0 CPU21 结果](verification/cpu21-results-2026-10-26.json)：历史 16 项固件验收。
- [外部源码哈希](verification/cpu21-source-hashes-2026-10-26.json)：只读核对快照。
- [0.3.0 结果](verification/scope-results-0.3.0-2026-10-26.json)：18 项固件验收与快照关联。
- [目录整理验证](verification/layout-results-2026-10-26.json)：迁移后 18 项固件回归、81 文件只读核对及常规检查摘要。
- [工作台截图](images/workbench.png)。

历史 JSON 纳入 Git；重新运行的固件、日志和结果写 `build/`，不覆盖历史证据。
