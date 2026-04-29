# Epic 总览

## 1. 定位

Epic 是能力域，不是时间盒。一个 Epic 可以跨多个 Sprint 推进；一个 Sprint 也可以同时承接多个 Epic 的 Backlog。本文只维护能力边界、版本归属和当前状态，具体执行计划以 `../sprints/` 下的 Sprint 文档为准。

## 2. 与其他规划对象的关系

| 对象 | 含义 | 主要维护位置 |
| --- | --- | --- |
| Milestone | 阶段关口，例如需求评审、设计评审、测试验收、上线复盘 | `../../01-项目管理/项目计划与里程碑.md` |
| Epic | 能力域或业务主题，承接一组 Backlog | 本目录与 `../产品待办清单.md` |
| Backlog | 可交付任务，编号为 `B-xxx` | `../产品待办清单.md` |
| Sprint | 固定周期内选择并交付的 Backlog 集合 | `../sprints/` |
| Release | 面向版本发布的范围、验收和遗留风险集合 | `../releases/` |

## 3. Epic 状态

| Epic | 能力域 | 版本 | 当前状态 | 主要 Sprint | 说明 |
| --- | --- | --- | --- | --- | --- |
| E0 | 工程启动 | V1.0 | Done | Sprint 01 | 前后端工程入口、配置、健康检查和本地验证链路已建立 |
| E1 | 用户与知识库基础 | V1.0 | Done | Sprint 02、Sprint 07 | 登录占位、用户/用户组、知识库基础和后续管理收口已完成 |
| E2 | 文档中心 | V1.0 | Done | Sprint 03、Sprint 08 | 文档上传元数据、版本、作业状态和详情接入已完成 |
| E3 | 配置中心 | V1.0 | Done | Sprint 04、Sprint 12 | Revision 保存/激活、Pipeline 校验和核心参数保存已完成 |
| E4 | QA Run 最小链路 | V1.0 | Done | Sprint 05、Sprint 12 | QARun 创建、状态轮询、详情、Trace 和参数生效链路已完成 |
| E5 | 真实 Provider 接入 | V1.0 | Done | Sprint 06、Sprint 13 | Provider 抽象已完成；真实连通性诊断仍在 Sprint 13 中收尾 |
| E6 | 权限与成员治理 | V1.0 | Done | Sprint 07、Sprint 12 | 成员绑定、权限摘要、ACL 和 Chunk 访问过滤已完成 |
| E7 | 文档生命周期与 Ingest Worker | V1.0 | Done | Sprint 08、Sprint 12 | 解析切块、重解析、active version 和同步状态已完成 |
| E8 | QA 历史与评估闭环 | V1.0/V1.1 | Partial | Sprint 09、Sprint 13 | 历史、回放、人工反馈和样本管理已完成；批量回归属于 V1.1 |
| E9 | 图检索分析与诊断 | V1.0 | Done | Sprint 10 | 图快照、实体路径、社区摘要和支撑 Chunk 诊断已完成 |
| E10 | 发布验收与运维治理 | V1.0 | Done | Sprint 11 | 审计日志、OpenAPI、依赖健康检查和发布检查脚本已完成 |
| E11 | 验收硬化 | V1.0 | Done | Sprint 12、Sprint 13 | 端到端验收脚本、权限回归、验收报告和依赖诊断均已完成 |
| E12 | RAG 质量闭环 | V1.0/V1.1 | Done | Sprint 12、Sprint 13 | P08 参数生效、EvaluationRun/Result、P10 评估结果视图已完成 |
| E13 | 配置优化闭环 | V1.1 | Done | Sprint 14 | 已打通配置差异对比、评估关联和优化草稿闭环 |
| E14 | Provider 生产化接入 | V1.2 | Todo | Sprint 15 | 补齐真实 Provider 凭据、诊断、限流和发布环境复测 |
| E15 | 知识库治理与文档质量 | V1.2 | Todo | Sprint 16 | 建立文档质量检查、批量治理和知识库健康概览 |
| E16 | 稳定性与观测 | V1.3 | Todo | Sprint 17 | 补齐运行指标、慢链路诊断、任务补偿和备份恢复演练 |
| E17 | 协作与治理增强 | V1.3 | Todo | Sprint 18 | 补齐配置发布记录、QA 协作、审计报表和有效权限解释 |

## 4. 本目录约定

- 本目录维护 Epic 层面的稳定说明，不存放 Sprint 计划。
- 与单个 Epic 强相关的验证说明可以保留在本目录，例如 `E1-本地验证说明.md` 和 `E2-本地验证说明.md`。
- 新增 Epic 时，先在 `../产品待办清单.md` 增加 Epic 和 Backlog，再在本文件补一行状态。
