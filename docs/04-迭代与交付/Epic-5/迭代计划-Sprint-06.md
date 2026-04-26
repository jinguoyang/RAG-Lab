# 迭代计划 Sprint 06

## 1. Sprint 基本信息

- Sprint 名称：Sprint 06
- Sprint 主题：E5 真实 Provider 接入起步
- 时间范围：待定
- 目标：先接入文档上传链路的 MinIO 原始文件存储，为后续解析、Embedding 和索引副本重建提供可追踪对象来源。

## 2. 关键假设

- Sprint 06 基于 Sprint 05 的 QA Run mock 链路继续推进。
- 本轮先完成 `B-021`，不一次性接入 Milvus、OpenSearch、Neo4j、LLM、Embedding 或 Rerank。
- 本地开发环境不强制启动 MinIO，默认 `metadata` 后端只记录对象引用；配置为 `minio` 后才写入真实 MinIO。
- PostgreSQL 仍是业务真值中心，MinIO 只保存原始文件和后续大体积产物。

## 3. 本 Sprint 目标

- 增加对象存储 Provider 抽象，服务层不直接依赖 MinIO SDK。
- 文档上传时先写入原始文件对象，再创建 `stored_files`、`documents`、`document_versions` 和 `ingest_jobs`。
- 增加 MinIO 运行配置和本地配置示例。
- 保持无 MinIO 环境下的最小本地联调能力。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S6-001 | B-021 | 接入 MinIO 原始文件存储 | P1 | 1d | Codex | Done |

## 5. 验收标准

- `RAG_LAB_STORAGE_BACKEND=metadata` 时，文档上传仍可创建可追踪的 `stored_files.object_key`。
- `RAG_LAB_STORAGE_BACKEND=minio` 且 MinIO 配置完整时，文档上传会写入 `RAG_LAB_STORAGE_BUCKET`。
- 数据库写入失败时，已写入的对象应尽力删除，避免明显孤儿对象。
- 后端应用代码可通过 Python 编译检查。

## 6. 范围边界

- 不实现文档解析 Worker。
- 不接入 Embedding、Milvus、OpenSearch、Neo4j、LLM 或 Rerank。
- 不调整前端文档中心交互。
- 不新增对象下载、预签名 URL 或对象生命周期管理接口。
