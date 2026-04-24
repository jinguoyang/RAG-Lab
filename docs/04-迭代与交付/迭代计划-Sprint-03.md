# 迭代计划 Sprint 03

## 1. Sprint 基本信息

- Sprint 名称：Sprint 03
- Sprint 主题：E2 文档中心最小链路
- 时间范围：待定
- 目标：完成文档、文档版本、IngestJob 的最小数据模型与接口，并让前端文档中心和文档详情页面接入真实数据。

## 2. 关键假设

- Sprint 03 基于 Sprint 02 已完成的开发期认证、用户、知识库和 PostgreSQL 迁移基础继续推进。
- 本 Sprint 先实现文档上传元数据链路：上传后创建 `Document`、`DocumentVersion` 和 `IngestJob`，不要求真实解析文件、生成 Chunk 或写入检索副本。
- 原始文件存储先采用开发期最小方案，只保证文件名、大小、类型、checksum 或存储引用等元数据可追踪；MinIO 正式接入留到 E5。
- 权限沿用 Sprint 02 的最小可见性规则：平台管理员可访问全部知识库，普通用户只访问自己负责的知识库；完整 ACL 和 Chunk 级权限留到后续迭代。

## 3. 本 Sprint 目标

- 新增文档、文档版本、IngestJob 相关迁移，字段与 `数据模型设计.md`、`数据库设计.md` 保持一致。
- 实现文档上传元数据接口，上传后立即生成文档对象、版本对象和 queued 作业。
- 实现文档列表、文档详情、版本列表、作业列表和作业详情接口。
- 前端 P06 文档中心、P07 文档详情接入真实接口，保留原型中必要的状态展示和空状态。
- 保持范围克制：不实现真实解析 Worker、Chunk 生成、active version 切换、重解析、外部对象存储或外部检索组件。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S3-001 | B-010 | 实现文档、文档版本、IngestJob 基础表与迁移 | P0 | 1.5d | Codex | Done |
| S3-002 | B-011 | 实现文档上传元数据接口，生成 Document、Version、IngestJob | P0 | 2d | Codex | Done |
| S3-003 | B-012 | 实现文档列表、详情、版本列表和作业状态接口 | P0 | 2d | Codex | Done |
| S3-004 | B-013 | 接入文档中心、文档详情和作业状态展示 | P0 | 2d |  | Todo |
| S3-005 | B-027 | 补充 E2 最小验证命令和文档中心联调说明 | P0 | 0.5d |  | Todo |

## 5. 建议实现顺序

1. 数据库迁移：新增 `stored_files`、`documents`、`document_versions`、`ingest_jobs`，先不创建 `chunks`，避免把本轮范围扩大到解析和检索。
2. 后端 Schema 与服务：新增文档、版本、作业 DTO，保持 API 字段使用 `camelCase`，数据库字段使用 `snake_case`。
3. 上传元数据接口：实现 `POST /api/v1/knowledge-bases/{kbId}/documents`，同一事务内创建文件记录、文档、版本和 queued 作业。
4. 查询接口：实现文档列表、文档详情、版本列表、作业列表和作业详情，列表默认按 `updatedAt` 或 `createdAt` 倒序。
5. 前端接入：沿用 Sprint 02 的 `types / services / adapters / pages` 分层，P06/P07 不直接散落后端 DTO 字段转换。
6. 验证与文档：补充迁移、上传、查询、前端构建和联调验证命令。

## 6. 验收标准

- 后端可以在 `rag-lab` Conda 环境下执行 Alembic 迁移到 `head`。
- 数据库中存在文档、版本、作业相关基础表和必要索引，状态字段约束与设计文档一致。
- `POST /api/v1/knowledge-bases/{kbId}/documents` 能创建文档、首个版本和 queued IngestJob。
- `GET /api/v1/knowledge-bases/{kbId}/documents` 能分页返回当前知识库下的文档摘要。
- `GET /api/v1/knowledge-bases/{kbId}/documents/{documentId}` 能返回文档详情和 active version 摘要。
- `GET /api/v1/knowledge-bases/{kbId}/documents/{documentId}/versions` 能返回版本列表。
- `GET /api/v1/knowledge-bases/{kbId}/ingest-jobs` 和 `GET /api/v1/knowledge-bases/{kbId}/ingest-jobs/{jobId}` 能返回作业状态。
- 前端 P06 文档中心能展示真实文档列表、上传后新增记录和最近作业。
- 前端 P07 文档详情能展示真实文档基础信息、版本列表和关联作业。
- 前端构建、后端编译和核心接口 TestClient 验证通过。

## 7. 范围边界

- 不接入 MinIO、Milvus、OpenSearch、Neo4j、Embedding 或 LLM 服务。
- 不实现真实文档解析、Chunk 生成、向量化、Sparse 索引或图构建。
- 不实现 active version 切换、重解析、失败重试和取消作业；接口可在后续 Sprint 补齐。
- 不实现完整 ACL、Chunk 级权限和成员权限后台管理。
- 不重构 P06/P07 的视觉结构，只做真实数据接入所需的最小改动。

## 8. 已确认信息

- E2 对应产品待办 `B-010` 至 `B-013`。
- 文档中心页面对应原型 P06，文档详情页面对应原型 P07。
- 上传接口来源为 `接口设计说明.md` 6.4，查询接口来源为 `接口设计说明.md` 5.5 和 5.6。
- PostgreSQL 仍是文档、版本、作业状态的业务真值中心。

## 9. 风险与阻塞

- 如果本轮同时接入真实文件存储、解析 Worker 和检索副本，E2 会从文档中心最小链路扩大成多组件联调。
- 如果文档、版本和作业创建不在同一事务内，上传失败或半成功会导致前端难以追踪状态。
- 如果前端页面直接依赖后端 DTO，后续补充 Chunk、重解析和 active version 切换时会增加返工。
- 如果作业状态枚举和设计文档不一致，后续 Worker、QA 调试和运维监控会出现状态映射混乱。

## 10. Sprint 输出物

- 文档、文档版本、IngestJob 最小表结构和迁移。
- 文档上传元数据接口。
- 文档列表、详情、版本列表、作业列表和作业详情接口。
- 前端 P06/P07 真实接口接入。
- E2 本地验证与联调说明。

## 11. 预设决策记录

### S3-001 文档中心最小数据范围

- 决策：Sprint 03 先落 `stored_files`、`documents`、`document_versions`、`ingest_jobs`，暂不落 `chunks`。
- 原因：本轮目标是让文档中心形成可上传、可查看、可追踪作业的最小链路；Chunk 生成依赖解析 Worker 和后续检索链路。
- 后续：实现真实解析后，再补 `chunks`、索引同步作业和 Chunk 查询接口。

### S3-002 上传元数据事务

- 决策：上传接口必须在同一数据库事务内创建文件记录、文档、版本和 queued 作业。
- 原因：前端 P06 需要在上传后立即看到文档对象和作业状态，失败时也要避免半成品数据污染。
- 后续：接入真实存储后，需要补充对象写入失败的补偿清理和审计记录。

### S3-003 开发期文件存储策略

- 决策：开发期优先保存可追踪的文件元数据和存储引用，不把 MinIO 作为 Sprint 03 的前置依赖。
- 原因：MinIO 属于 E5 外部 Provider 接入范围，过早接入会增加本轮环境排障成本。
- 后续：E5 接入 MinIO 时，`stored_files` 继续作为对象存储引用真值表。

### S3-004 前端接入分层

- 决策：前端继续沿用 `types / services / adapters / pages` 分层接入 Documents 和 IngestJobs。
- 原因：页面 ViewModel 需要和后端 DTO 解耦，避免后续版本、Chunk、重解析字段扩展时污染页面层。
- 后续：S3-004 完成后，P05 知识库概览的最近作业区可复用 IngestJob service。
