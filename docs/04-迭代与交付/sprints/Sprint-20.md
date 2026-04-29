# 迭代计划 Sprint 20

## 1. Sprint 基本信息

- Sprint 名称：Sprint 20
- Sprint 主题：真实多副本写入与入库状态
- 涉及 Epic：E18 真实入库与多副本构建
- 建议版本：V1.4
- 时间范围：待定
- 目标：把 Chunk 真实写入 Milvus、OpenSearch 和 Neo4j，并把 Index Sync 从记录型能力升级为真实执行型 Worker。

## 2. 关键假设

- Sprint 19 已产出结构化 Chunk payload 和真实 Embedding。
- Milvus、OpenSearch、Neo4j 均通过 Provider/Adapter 封装，不让业务服务直接散落 SDK 细节。
- 检索副本可重建，失败时以 PostgreSQL Chunk 真值为恢复来源。
- 外部依赖不可用时，验证脚本允许记录环境限制，但代码路径必须具备真实写入能力。

## 3. 本 Sprint 目标

- Chunk 向量真实 upsert 到 Milvus，并支持重解析、停用和删除同步。
- Chunk 文本、metadata 和过滤字段真实 upsert 到 OpenSearch。
- 基于真实 LLM 抽取实体关系，写入 Neo4j Entity、Relation 和 ChunkRef。
- P05/P06/P07 展示 parse、embedding、milvus、opensearch、neo4j 各阶段状态。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S20-001 | B-085 | 将 Chunk 向量真实写入 Milvus 并支持删除同步 | P0 | 2d | Codex | Todo |
| S20-002 | B-086 | 将 Chunk 文本和过滤字段真实写入 OpenSearch | P0 | 2d | Codex | Todo |
| S20-003 | B-087 | 基于真实 LLM 抽取实体关系并写入 Neo4j | P0 | 2d | Codex | Todo |
| S20-004 | B-088 | 将 Index Sync 从记录型改为真实执行型 Worker | P0 | 1.5d | Codex | Todo |
| S20-005 | B-089 | 完善 P05/P06/P07 入库阶段状态和失败原因展示 | P1 | 1d | Codex | Todo |
| S20-006 | B-090 | 建立 V1.4 真实入库验收脚本和样例数据 | P0 | 1d | Codex | Todo |

## 5. 验收标准

- 一个真实文档完成入库后，PostgreSQL、Milvus、OpenSearch 和 Neo4j 均能按 chunk_id 或支撑关系追溯。
- 重解析后旧版本副本不再被 active 查询使用，新版本副本状态可见。
- 任一副本写入失败时，IndexSyncJob 标记 failed，页面展示失败 store、错误码和可重试入口。
- V1.4 验收脚本能检查真实入库主链路和可选外部依赖限制。

## 6. 范围边界

- 不实现 QA 检索查询主链路，V1.5 承接。
- 不把 Neo4j 的实体关系作为最终 Evidence。
- 不要求外部依赖在本地开发机永久运行，但必须提供可复测配置和脚本。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Sprint 20 验证脚本：`conda run -n rag-lab python scripts/verify_sprint20_real_indexes.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`
