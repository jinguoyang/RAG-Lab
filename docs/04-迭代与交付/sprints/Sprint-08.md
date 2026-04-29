# 迭代计划 Sprint 08

## 1. Sprint 基本信息

- Sprint 名称：Sprint 08
- Sprint 主题：E7 文档生命周期与 Ingest Worker
- 时间范围：待定
- 目标：围绕 Chunk 真值、重解析、active version 切换、作业重试取消和副本同步状态，完成 P07 文档详情可联调的最小闭环。

## 2. 关键假设

- Sprint 08 基于 Sprint 07 的权限摘要与 ChunkAccessFilter 继续推进。
- 本轮完成 `B-035` 至 `B-038`。
- PostgreSQL 是 Chunk 正文真值中心；Milvus、OpenSearch、Neo4j 在本轮先以 `index_sync_jobs` / `index_sync_records` 记录可重建副本状态。
- Worker 先采用后端本地同步执行器，保证无 Redis / Celery / 外部索引服务时仍可完成本地验证。
- 生产级异步队列、外部索引真实写入和审计查询页面不在本 Sprint 范围内。

## 3. 本 Sprint 目标

- 创建 `chunks` 真值表、文档生命周期审计表、索引同步作业表和同步记录表。
- 实现上传后解析切块、Chunk 写入 PostgreSQL、访问过滤摘要生成和本地副本同步状态记录。
- 实现文档重解析、active version 切换、IngestJob 重试与取消。
- 实现副本重建入口，支持基于 PostgreSQL Chunk 真值创建 rebuild 作业。
- 接入 P07 Chunk 分页、Chunk 详情、版本切换二次确认和作业操作反馈。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S8-001 | B-035 | 实现文档解析与切块 Worker，将 Chunk 正文写入 PostgreSQL | P0 | 1d | Codex | Done |
| S8-002 | B-036 | 实现重解析、作业重试/取消、active version 切换和审计 | P0 | 1d | Codex | Done |
| S8-003 | B-037 | 实现 index_sync_jobs / index_sync_records 的副本同步状态和重建入口 | P1 | 1d | Codex | Done |
| S8-004 | B-038 | 接入文档详情 Chunk 分页、版本切换确认和作业重试反馈 | P0 | 1d | Codex | Done |

## 5. 验收标准

- 上传文本文档后可生成 active version 和 Chunk 记录，Chunk 正文保存在 PostgreSQL。
- 文档详情页可分页查看 Chunk，并可打开抽屉查看完整正文与 metadata。
- 重解析会生成新版本和新作业，旧版本与旧 Chunk 保留可追溯。
- active version 切换必须要求二次确认，并写入审计日志。
- 失败或取消的 IngestJob 可重试，queued / running 作业可取消。
- 副本同步状态可通过 `index_sync_jobs` 和 `index_sync_records` 追踪，支持 rebuild 入口。
- 后端应用代码可通过 Python 编译检查，前端可通过 Vite 构建。

## 6. 范围边界

- 不引入 Celery / Redis 生产任务队列。
- 不真实写入 Milvus、OpenSearch 或 Neo4j，仅记录本地同步成功状态和重建作业。
- 不实现完整审计日志查询页面，审计表先支撑文档生命周期高风险操作。
- 不实现 PDF、Word 等复杂格式的高保真解析；非文本文件会生成可追踪占位 Chunk。
