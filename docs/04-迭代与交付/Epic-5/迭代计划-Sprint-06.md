# 迭代计划 Sprint 06

## 1. Sprint 基本信息

- Sprint 名称：Sprint 06
- Sprint 主题：E5 真实 Provider 接入起步
- 时间范围：待定
- 目标：完成 E5 真实 Provider 接入的最小后端闭环，覆盖 MinIO、Embedding、Milvus、OpenSearch、Neo4j、LLM 和 Rerank 的配置、Provider 抽象与 QA 编排调用。

## 2. 关键假设

- Sprint 06 基于 Sprint 05 的 QA Run mock 链路继续推进。
- 本轮完成 `B-021` 至 `B-025`。
- 本地开发环境不强制启动 MinIO、Milvus、OpenSearch、Neo4j 或模型服务；默认使用本地降级 Provider，配置真实后端后才调用外部组件。
- PostgreSQL 仍是业务真值中心，MinIO 只保存原始文件和后续大体积产物。
- 当前仓库尚未落地 Chunk 表和解析 Worker，因此本 Sprint 不承诺完整“解析 -> 切块 -> 建索引”的异步链路，只完成 QA 运行时 Provider 接入和图快照元数据。

## 3. 本 Sprint 目标

- 增加对象存储 Provider 抽象，服务层不直接依赖 MinIO SDK。
- 文档上传时先写入原始文件对象，再创建 `stored_files`、`documents`、`document_versions` 和 `ingest_jobs`。
- 增加 Embedding、Dense、Sparse、Graph、LLM、Rerank Provider 抽象和配置。
- QA Run 执行链路通过 Provider 编排，并在外部组件未启用时保留本地可验证降级。
- 增加 GraphSnapshot / GraphChunkRef 元数据表和最小查询接口。
- 保持无外部组件环境下的最小本地联调能力。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S6-001 | B-021 | 接入 MinIO 原始文件存储 | P1 | 1d | Codex | Done |
| S6-002 | B-022 | 接入 Embedding 与 Milvus Dense 检索 Provider | P1 | 1d | Codex | Done |
| S6-003 | B-023 | 接入 OpenSearch Sparse 检索 Provider | P1 | 1d | Codex | Done |
| S6-004 | B-024 | 接入 Neo4j Graph Retrieval Provider 和图快照元数据 | P1 | 1d | Codex | Done |
| S6-005 | B-025 | 接入 LLM / Rerank Provider，并替换 mock 生成链路 | P1 | 1d | Codex | Done |

## 5. 验收标准

- `RAG_LAB_STORAGE_BACKEND=metadata` 时，文档上传仍可创建可追踪的 `stored_files.object_key`。
- `RAG_LAB_STORAGE_BACKEND=minio` 且 MinIO 配置完整时，文档上传会写入 `RAG_LAB_STORAGE_BUCKET`。
- QA Run Trace 能体现 queryRewrite、denseRetrieval、sparseRetrieval、graphRetrieval、rerank、permissionFilter、generation 和 citation 步骤。
- 外部 Provider 未启用或失败时，QA Run 可以以 `partial` 或本地降级结果收口，并在 Trace / Metrics 中记录原因。
- GraphSnapshot 元数据可迁移、可分页查询。
- 数据库写入失败时，已写入的对象应尽力删除，避免明显孤儿对象。
- 后端应用代码可通过 Python 编译检查。

## 6. 范围边界

- 不实现文档解析 Worker。
- 不调整前端文档中心交互。
- 不新增对象下载、预签名 URL 或对象生命周期管理接口。
- 不实现 Milvus / OpenSearch / Neo4j 的索引构建 Worker。
- 不在没有 Chunk 表的情况下伪造完整权限回表裁剪；本 Sprint 只保留编排位置和 Trace 诊断。
