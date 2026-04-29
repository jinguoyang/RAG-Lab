# 04 迭代与交付

本目录承接敏捷执行和版本交付视角，用于管理 Epic、Backlog、Sprint、Release 和编码规范。

## 1. 规划对象

| 对象 | 定义 | 维护位置 |
| --- | --- | --- |
| Epic | 能力域或业务主题，不是时间盒 | [epics/README](./epics/README.md) |
| Backlog | 可交付任务，编号为 `B-xxx` | [产品待办清单](./产品待办清单.md) |
| Sprint | 固定周期内选择并交付的 Backlog 集合 | [sprints/README](./sprints/README.md) |
| Release | 面向版本发布的范围、验收和风险集合 | [releases/README](./releases/README.md) |
| 编码规范 | 开发、命名、注释、验证和 Git 约定 | [编码规范](./编码规范.md) |

核心约定：**Epic 表示做什么能力，Sprint 表示什么时候交付哪些 Backlog。二者不是一一对应关系。**

## 2. 推荐节奏

- 每个 Sprint 开始前，从产品待办清单中选择本轮 Backlog，并写入对应 Sprint 文档。
- 每周更新 Backlog 优先级和状态。
- 每个 Backlog 完成后，同步更新产品待办清单；若本 Sprint 已完成，也更新 Sprint 文档结果。
- 每个 Sprint 结束后，沉淀实际完成项、验证结果、遗留问题和下一步建议。
- 每个 Release 发布前，更新版本范围、验收结果和遗留风险。

## 3. 文档入口

- [产品待办清单](./产品待办清单.md)
- [Epic 总览](./epics/README.md)
- [Sprint 总览](./sprints/README.md)
- [Release 总览](./releases/README.md)
- [中长期开发规划](./中长期规划.md)
- [编码规范](./编码规范.md)

## 4. 当前状态

- V1.0 主功能闭环已经完成，Sprint 12 已完成验收硬化和参数生效。
- V1.1 范围（B-058、B-060、B-061、B-062、B-063、B-064）已完成并完成最小验证。
- Sprint 15-18 作为后续中长期规划，分别覆盖 Provider 生产化、知识库治理、稳定性观测和协作治理。
