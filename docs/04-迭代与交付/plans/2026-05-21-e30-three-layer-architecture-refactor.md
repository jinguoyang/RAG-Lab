# E30 三层架构模型收口实施计划

本文档为开发计划，用于安排在原项目上演进文档库、知识库、智能应用三层架构模型的后续实施工作。本文只规划开发范围、顺序和验收口径，不替代详细接口、数据库迁移或页面设计。

## 1. 背景与目标

当前项目已经具备文档库、知识库、RAG App、真实入库、QA 历史和 App Runtime 等基础能力，不建议另起新项目。E30 的目标是在原项目上分阶段收口三层模型：

- 文档库：源文件资产层，负责文件、版本、解析产物、预览、下载、重复提醒和文档库权限。
- 知识库：知识加工层，负责选择具体文档版本和解析版本，生成 BindingRevision、Chunk、索引副本和 QA 能力。
- 智能应用：外部发布层，负责 API Key、Runtime 调用、调用记录、统计和应用级治理。

## 2. 关键假设

- 技术栈保持不变，继续使用现有 FastAPI、React、PostgreSQL、对象存储和检索副本体系。
- 不另起新仓库，不重写已有前后端工程。
- 以 PostgreSQL 业务表为真值，Milvus、OpenSearch、Neo4j 仍作为检索副本。
- 文档库不自动改变知识库当前使用版本，知识库绑定版本切换必须走独立流程。
- 普通用户界面不暴露独立 ParseRevision 删除入口。
- QA 历史保留运行事实；被清理的引用源展示“引用文件已被清理”。

## 3. 范围

### 3.1 本次包含

- 三层模型和数据结构收口。
- 角色权限码和跨资源权限校验收口。
- DocumentVersion、ParseRevision、BindingRevision、Chunk 生命周期改造。
- 文档版本删除影响分析、强确认和下游清理。
- QA Evidence source_deleted 展示。
- 知识库 disabled 对 App Runtime 的保护。
- 文档库、知识库、智能应用相关前端页面的必要交互调整。
- 后端、前端、迁移、权限和端到端回归验证。

### 3.2 本次不包含

- 不更换技术栈。
- 不重写前端页面体系。
- 不引入显式 deny。
- 不做字段级 ABAC。
- 不实现跨版本对比检索。
- 不实现自动生命周期清理策略。
- 不将 App Runtime 改造成自由工作流或多知识库任意编排。

## 4. 设计依据

- `docs/04-迭代与交付/specs/2026-05-20-permission-role-model-design.md`
- `docs/04-迭代与交付/specs/2026-05-21-document-version-parse-revision-deletion-design.md`
- `docs/04-迭代与交付/specs/2026-05-21-knowledge-base-chunk-management-design.md`
- `docs/04-迭代与交付/specs/2026-05-21-document-kb-app-architecture-briefing.md`

## 5. 分阶段计划

| Sprint | 主题 | 目标 | Backlog |
| --- | --- | --- | --- |
| Sprint 40 | 模型基线与权限收口 | 先稳定迁移边界、核心表结构和权限判定 | B-197 至 B-201 |
| Sprint 41 | 后端生命周期改造 | 打通 ParseRevision、BindingRevision、Chunk、删除和 Runtime 状态保护 | B-202 至 B-208 |
| Sprint 42 | 前端三层体验改造 | 让用户能看懂三层关系、版本切换、删除影响和权限来源 | B-209 至 B-213 |
| Sprint 43 | 回归验收与文档同步 | 用端到端验证证明新模型可运行，并同步系统设计入口 | B-214 至 B-217 |

## 6. 关键风险

| 风险 | 影响 | 控制方式 |
| --- | --- | --- |
| 历史 Chunk 正文和 parsed_chunks 存储方式与目标模型不一致 | 迁移后 QA 回溯或检索异常 | Sprint 40 先做回填脚本和迁移测试 |
| 权限从知识库中心扩展为三层资源角色 | 跨资源操作可能误放权或误拒绝 | 先补权限矩阵测试，再接入业务服务 |
| BindingRevision 切换影响线上检索 | 可能出现半成品 Chunk 进入检索 | 采用先构建后激活，失败保持旧 active 可用 |
| 删除级联触达对象多 | 可能误删 active 数据或残留检索副本 | 删除前影响分析，active 和 running 场景禁止删除 |
| 前端概念增加 | 用户理解成本上升 | 普通入口只暴露文档、文档版本和知识库绑定版本，不暴露 ParseRevision 细节 |

## 7. 验收总标准

- 文档上传后可以生成 ParseRevision，并可被知识库选择入库。
- 知识库绑定明确指向 active BindingRevision。
- 默认检索只使用 active BindingRevision 下的 active Chunk。
- 删除正在支撑 active BindingRevision 的文档版本必须失败。
- 删除仅被历史 QA 引用的旧版本需要强确认，删除后历史 QA 展示“引用文件已被清理”。
- 用户直接角色和用户组角色在同一资源内按 allow 并集生效。
- 绑定文档到知识库必须同时校验文档库和知识库权限。
- 知识库 disabled 时 App Runtime 拒绝新调用，但不删除 App 和 Key。
- 前端能解释文档库、知识库、智能应用三层边界和操作影响。

## 8. 推荐验证命令

后续各 Sprint 至少执行：

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests
conda run -n rag-lab python scripts/export_openapi.py
```

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

文档类改动执行：

```powershell
git diff --check
```
