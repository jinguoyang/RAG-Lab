# 04 迭代与交付

本目录承接敏捷执行和版本交付视角。为避免文档重复和状态漂移，本目录采用“一个状态只维护一个源头”的规则。

## 1. 概念口径

| 对象 | 定义 | 状态源 |
| --- | --- | --- |
| Epic | 能力域或业务主题，不是时间盒 | [产品待办清单](./产品待办清单.md) |
| Backlog | 最小可跟踪交付项，编号为 `B-xxx` | [产品待办清单](./产品待办清单.md) |
| Sprint | 时间盒和执行记录，承接一组 Backlog | [Sprint 总览](./sprints/README.md) |
| Release | 面向发布判断的范围、验收和风险集合 | [Release 总览](./releases/README.md) |

核心约定：**Epic 表示做什么能力，Sprint 表示什么时候交付哪些 Backlog，Release 表示能否发布。三者不是一一对应关系。**

## 2. 当前状态

- V1.0 至 V1.7 的 Backlog、Epic、Sprint 和 Release 已收口为完成。
- 最新完成范围是 E22：知识库治理工作流强化，已通过 Sprint 27 至 Sprint 29 补齐治理操作、诊断详情和治理后验证入口。
- 当前没有进行中的 Sprint；后续新工作应先进入产品待办清单，再建立新的 Sprint 或 Release 计划。
- 发布前仍需在目标测试或预生产环境补齐真实 Provider 网络级复测记录，入口见 [V1.7 Provider 网络级复测记录](../06-发布与运维/V1.7-Provider网络级复测记录.md)。

## 3. 文档分层

### 3.1 活文档

这些文档是后续开发和发布判断的主要入口：

- [产品待办清单](./产品待办清单.md)：Backlog 和 Epic 状态源。
- [Sprint 总览](./sprints/README.md)：当前 Sprint 和历史 Sprint 索引。
- [Release 总览](./releases/README.md)：Release 状态源。
- [编码规范](./编码规范.md)：开发、命名、注释、验证和 Git 约定。
- [V1.7 RAG 调优指南](../06-发布与运维/V1.7-RAG调优指南.md)：当前 RAG 参数调优说明。

### 3.2 历史归档

这些文档保留历史计划、执行证据和验收口径，通常不再反复同步状态：

- `sprints/sprint1-20/Sprint-01.md` 至 `sprints/sprint1-20/Sprint-20.md`
- `sprints/sprint21-40/Sprint-21.md` 至 `sprints/sprint21-40/Sprint-29.md`
- `releases/V1.0-*.md` 至 `releases/V1.7-*.md`
- [中长期规划](./中长期规划.md)
- `docs/superpowers/specs/` 和 `docs/superpowers/plans/`

历史归档中出现旧计划、旧假设或当时的“待定”字样时，一般保留原貌；只在它会误导当前入口时补充归档说明。

## 4. 维护规则

- 不在多个文档重复维护同一状态表。
- Backlog 或 Epic 状态变化，只更新 [产品待办清单](./产品待办清单.md)，必要时在总览文档增加链接说明。
- Sprint 是否进行中或完成，只更新 [Sprint 总览](./sprints/README.md)；单个 Sprint 文档作为执行记录保留。
- Release 是否完成，只更新 [Release 总览](./releases/README.md)；单个 Release 文档作为范围和验收记录保留。
- 真实 Provider 网络级复测结果只回填到发布运维记录，不用 local/mock 结果替代真实环境结论。
- 新增文档前先确认是否能补充到现有入口；确需新增时，文档开头应说明它是活文档还是历史归档。
