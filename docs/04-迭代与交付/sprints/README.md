# Sprint 总览

Sprint 是时间盒，用于承接一轮可验证交付。本文维护当前 Sprint 状态和历史 Sprint 索引，不再重复保存每个 Sprint 的完整计划表。

## 1. 当前状态

- Sprint 35 已完成，主题为前端动作驱动的真实数据验收硬化，所有 Backlog（B-146、B-150 至 B-155）已 Done。
- Sprint 36 已完成，主题为文档库基础框架与文档解析，实现数据库迁移、上传/列表/详情 API、P15/P16 前端页面、PDF/Markdown 预览组件和验收脚本。
- Sprint 37 已完成，主题为 E28 文档库后续功能：文本预览 API、绑定服务、分块向量化、文档删除、重试机制、TXT/DOCX 预览组件和使用情况查询。
- Sprint 38 已完成，主题为 E28 文档库增强：权限收口、批量操作、自动重试、统计端点、RBAC 权限检查和前端统计卡片。
- Sprint 39 已完成，主题为 E29 UI 一致性统一。
- Sprint 40 已完成，主题为 E30 三层架构基线：ParseRevision/ChunkRevision 表创建、chunks/document_kb_bindings 表结构改造、权限收口和数据迁移。
- Sprint 41 已完成，主题为 E30 后端生命周期改造：ParseRevision 创建、文件 hash 重复检查、source_status 字段和三层架构后端重构。
- Sprint 42 已完成，主题为 E30 前端体验改造：删除影响分析、版本选择器、证据回溯链路、成员权限页面和应用管理增强。
- Sprint 43 已完成，主题为 E30 回归验收：Playwright E2E 测试基础设施、主链路/删除/权限回归测试和文档同步检查。
- Sprint 44 已完成，主题为 E31 图片 RAG 第一阶段：VisionTextProvider 抽象、图片解析 Pipeline、图片 Chunk 入库和 Citation 来源回溯。
- Sprint 45 已完成，主题为 BindingRevision → ChunkRevision 后端重命名：DB 迁移、标识符全量替换、strategy/params 字段化、rechunk API 和单元测试。
- Sprint 46 待开发，主题为 ChunkRevision 前端改造与文档同步。
- Sprint 47 已完成，主题为 E32 场景化智能应用模型基线：内置场景模板、应用场景元数据、推荐 ConfigRevision 和 P13 场景展示。
- Sprint 48 已完成，主题为 E32 场景向导与知识库问答助手：P13 场景助手创建、短期 Embed Token、嵌入页、问答反馈和 retrieve 证据摘要。
- Sprint 49 至 Sprint 50 已完成，主题为 E32 场景化智能应用后续能力：员工培训助手、培训测验、培训报告、验收硬化和文档同步。
- Sprint 51 已完成，主题为 E32 语义检索 + LLM 测验生成：Milvus 向量语义检索、LLM 智能出题、LLM 结构化讲解和模板回退。
- Sprint 52 待开发，已按 E33 新口径重排为平台课堂 Agent 基线：多轮对话、课堂状态机、受控答疑和结构化课堂事件 API；原自适应培训和掌握度计划降为低优先级后续。
- Sprint 53 待开发，已按 E33 新口径重排为外部培训应用基线：独立项目、数据库迁移、平台接入和学习计划审核 UI；原嵌入页 SSE、Markdown 和运营分析计划降为低优先级后续。
- Sprint 54 已完成，主题为 E31 mimo-v2.5 图片 Provider 对齐与样本问答验收硬化：对齐小米图片理解 API、记录安全 usage 摘要，并用两张 `docs/examples` 图片验证问答召回。
- Sprint 55 待开发，主题为 E33 平台结构化学习计划：岗位描述生成学习计划、AI 草稿校验、平台业务数据落库和学习计划版本快照。
- Sprint 56 待开发，主题为 E33 题库生成与审核：练习题/认证题草稿、认证题审核门禁、rubric 和题库发布。
- Sprint 57 待开发，主题为 E33 外部培训应用课堂交互：题库审核页面、课堂页面、A/B/C/D 结构化答题组件和事件提交。
- Sprint 58 待开发，主题为 E33 员工培训 Agent 端到端验收：计划生成、审核、上课、答题、追溯和文档同步。
- 下一版本为 V1.9，计划承接 E23 图快照保留与配置治理、E24 文档解析能力增强；E27 RAG App 运行治理与接入可见性已完成。E28 文档库功能已全部完成。
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
| Sprint 37 | 文档库 V1.0 | 文档预览完善、知识库绑定和绑定后切块向量化 | Done | `sprint21-40/Sprint-37.md` |
| Sprint 38 | 文档库 V1.0 | 权限收口、批量操作、大文件体验、错误处理和测试覆盖 | Done | `sprint21-40/Sprint-38.md` |
| Sprint 39 | UI V1.1 | UI/交互风格统一 — 文档库、应用中心、字典管理对齐知识库 | Done | `sprint21-40/Sprint-39.md` |
| Sprint 40 | 架构演进 V2.0 | 三层架构模型基线与权限收口 | Done | `sprint21-40/Sprint-40.md` |
| Sprint 41 | 架构演进 V2.0 | 三层架构后端生命周期改造 | Done | `sprint41-60/Sprint-41.md` |
| Sprint 42 | 架构演进 V2.0 | 三层架构前端体验改造 | Done | `sprint41-60/Sprint-42.md` |
| Sprint 43 | 架构演进 V2.0 | 三层架构回归验收与文档同步 | Done | `sprint41-60/Sprint-43.md` |
| Sprint 44 | 多模态 RAG Phase 1 | 图片 RAG 第一阶段：视觉文本 Chunk 闭环 | Done | `sprint41-60/Sprint-44.md` |
| Sprint 45 | 架构演进 V2.0 | BindingRevision → ChunkRevision 后端重命名与 Rechunk | Done | `sprint41-60/Sprint-45.md` |
| Sprint 46 | 架构演进 V2.0 | ChunkRevision 前端改造与文档同步 | Ready | `sprint41-60/Sprint-46.md` |
| Sprint 47 | 场景化智能应用 | 场景模板与智能应用模型基线 | Done | `sprint41-60/Sprint-47.md` |
| Sprint 48 | 场景化智能应用 | 场景向导与知识库问答助手 | Done | `sprint41-60/Sprint-48.md` |
| Sprint 49 | 场景化智能应用 | 员工培训助手运行时 | Done | `sprint41-60/Sprint-49.md` |
| Sprint 50 | 场景化智能应用 | 验收硬化与文档同步 | Done | `sprint41-60/Sprint-50.md` |
| Sprint 51 | 场景化智能应用 | 语义检索 + LLM 测验生成 | Done | `sprint41-60/Sprint-51.md` |
| Sprint 52 | 员工培训 Agent 深化 | 平台课堂 Agent 基线 | Todo | `sprint41-60/Sprint-52.md` |
| Sprint 53 | 员工培训 Agent 深化 | 外部培训应用基线 | Todo | `sprint41-60/Sprint-53.md` |
| Sprint 54 | 多模态 RAG Phase 1 硬化 | mimo-v2.5 图片 Provider 对齐与样本问答验收 | Done | `sprint41-60/Sprint-54.md` |
| Sprint 55 | 员工培训 Agent 深化 | 平台结构化学习计划 | Todo | `sprint41-60/Sprint-55.md` |
| Sprint 56 | 员工培训 Agent 深化 | 题库生成与审核 | Todo | `sprint41-60/Sprint-56.md` |
| Sprint 57 | 员工培训 Agent 深化 | 外部培训应用课堂交互 | Todo | `sprint41-60/Sprint-57.md` |
| Sprint 58 | 员工培训 Agent 深化 | 员工培训 Agent 端到端验收 | Todo | `sprint41-60/Sprint-58.md` |

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
