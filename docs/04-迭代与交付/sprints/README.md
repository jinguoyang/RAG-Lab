# Sprint 总览

Sprint 是时间盒，用于承接一轮可验证交付。本文维护当前 Sprint 状态和历史 Sprint 索引，不再重复保存每个 Sprint 的完整计划表。

## 1. 当前状态

- Sprint 35 已完成，主题为前端动作驱动的真实数据验收硬化，所有 Backlog（B-146、B-150 至 B-155）已 Done。
- Sprint 36 已完成，主题为文档库基础框架与文档解析，实现数据库迁移、上传/列表/详情 API、P15/P16 前端页面、PDF/Markdown 预览组件和验收脚本。
- Sprint 37 至 Sprint 38 已规划，主题为 E28 文档库后续功能，范围见 [E28 文档库功能实施计划](../plans/2026-05-19-e28-document-library.md)。
- 下一版本为 V1.9，计划承接 E23 图快照保留与配置治理、E24 文档解析能力增强；E27 RAG App 运行治理与接入可见性已完成。E28 文档库功能作为后续文档库 V1.0 规划进入 Sprint 36 至 Sprint 38。
- Sprint 01 至 Sprint 26 已完成，对应 V1.0 至 V1.7。
- Sprint 27 至 Sprint 29 已完成 E22 知识库治理工作流强化范围：P05 支持治理问题定位和治理后验证摘要，P06 支持批量治理和索引同步作业，P07 支持 Chunk 治理标记、索引重建和作业查看。
- Sprint 30 已完成 E25 的第一轮交付：RAG 应用定义、App API Key、blocking 对话接口、会话/消息/调用记录和最小接口抽样验证。
- Sprint 31 已完成 P13 RAG App 管理端入口、API Key 管理、调用记录和会话摘要；Sprint 32 已完成 App Runtime 安全边界设计和真实 Provider 轻量网络级复测；Sprint 33 至 Sprint 34 已完成 V1.8 后续计划，覆盖生产化能力、治理回流与架构预留评估。
- Sprint 35 已完成，聚焦前端真实动作触发 App Runtime、反馈回流、调用审计、QA 历史回溯和真实 Provider 端到端验收硬化。
- 后续新增工作应先进入 [产品待办清单](../产品待办清单.md)，再建立新的 Sprint 文档。
- 所有开发计划和设计规范统一存放在 `docs/04-迭代与交付/plans/` 和 `docs/04-迭代与交付/specs/` 下，不再维护独立的计划目录。

## 2. 历史 Sprint 索引

| Sprint 范围 | 版本 | 主题 | 状态 | 明细 |
| --- | --- | --- | --- | --- |
| Sprint 01-12 | V1.0 | 工程启动、基础业务、文档中心、配置中心、QA、权限、验收硬化 | Done | `sprint1-20/Sprint-01.md` 至 `sprint1-20/Sprint-12.md` |
| Sprint 13-14 | V1.0 / V1.1 | Provider 诊断、质量回归、配置优化闭环 | Done | `sprint1-20/Sprint-13.md`、`sprint1-20/Sprint-14.md` |
| Sprint 15-18 | V1.2 / V1.3 | Provider 生产化、知识库治理、稳定性观测、协作治理 | Done | `sprint1-20/Sprint-15.md` 至 `sprint1-20/Sprint-18.md` |
| Sprint 19-22 | V1.4 / V1.5 | 真实入库、多副本写入、真实检索、回放复跑 | Done | `sprint1-20/Sprint-19.md` 至 `sprint21-40/Sprint-22.md` |
| Sprint 23-26 | V1.6 / V1.7 | 真实 RAG 端到端闭环、模块化调优、评估对比 | Done | `sprint21-40/Sprint-23.md` 至 `sprint21-40/Sprint-26.md` |
| Sprint 27-29 | 内部增强 | 知识库治理工作流、诊断可操作化、治理后验证 | Done | `sprint21-40/Sprint-27.md` 至 `sprint21-40/Sprint-29.md` |
| Sprint 30 | V1.8 | RAG 应用运行时最小链路 | Done | `sprint21-40/Sprint-30.md` |
| Sprint 31 | V1.8 | RAG App 管理端与调用可见性 | Done | `sprint21-40/Sprint-31.md` |
| Sprint 32 | V1.8 | App Runtime 安全边界与真实 Provider 复测 | Done | `sprint21-40/Sprint-32.md` |
| Sprint 33 | V1.8 | App Runtime 生产化能力 | Done | `sprint21-40/Sprint-33.md` |
| Sprint 34 | V1.8 | App Runtime 治理回流与输入能力评估 | Done | `sprint21-40/Sprint-34.md` |
| Sprint 35 | V1.8 收尾 | 前端动作驱动的真实数据验收硬化 | Done | `sprint21-40/Sprint-35.md` |
| Sprint 36 | 文档库 V1.0 | 文档库基础模型、上传、文本提取和 PDF/Markdown 预览 | Done | `sprint21-40/Sprint-36.md` |
| Sprint 37 | 文档库 V1.0 | 文档预览完善、知识库绑定和绑定后切块向量化 | Planned | `sprint21-40/Sprint-37.md` |
| Sprint 38 | 文档库 V1.0 | 权限收口、批量操作、大文件体验、错误处理和测试覆盖 | Planned | `sprint21-40/Sprint-38.md` |

## 3. 单个 Sprint 文档约定

单个 Sprint 文档是历史执行记录，至少保留：

- Sprint 基本信息和涉及 Epic。
- 关键假设和范围边界。
- 计划事项，逐项关联 Backlog。
- 验收标准和验证命令。
- Sprint 结束后的实际结果、遗留问题和下一步建议。

## 4. 维护规则

- 当前 Sprint 状态只在本文件维护。
- 单个 Sprint 文档完成后作为归档记录，不再为了同步总览状态而反复改写。
- 若历史 Sprint 文档与当前实现存在差异，以产品待办清单、Release 总览和当前测试计划中的验证命令为准；历史 `verify_*.py` 脚本已归档清理。
