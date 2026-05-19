# V1.4 / V1.5 真实 RAG 链路设计

## 1. 背景

V1.3 已完成稳定性、观测和协作治理，但当前实现仍保留较多 local、mock 和占位链路。下一阶段不继续扩展生产治理能力，而是补齐现有程序的真实功能链路：上传后真实解析和多副本构建，查询时真实检索、生成、引用和回放复跑。

## 2. 设计目标

- V1.4：上传文件后真实解析、切分 Chunk、生成 Embedding，并写入 PostgreSQL、Milvus、OpenSearch 和 Neo4j。
- V1.5：QA 调试基于真实 Dense、Sparse、Graph 和 LLM API 链路执行，并完善历史回放、复跑和差异对比。
- 真实 LLM API 接入作为基础能力进入 V1.4，同时服务 Embedding、图谱抽取、Query Rewrite 和 Generation。

## 3. 非目标

- 不建设生产认证、SSO、审批流、通知中心、多租户和成本结算。
- 不引入任意 HTTP 工具节点、自定义 Python 节点或自由 DAG。
- 不把 Milvus、OpenSearch、Neo4j 作为业务真值。
- 不允许真实 Provider 配置下静默降级为 local/mock 并标记成功。

## 4. V1.4 设计

### 4.1 入库流程

1. 用户在 P06 上传 txt、md、pdf 或 docx。
2. 后端保存原始文件到对象存储，并创建 Document、DocumentVersion、IngestJob。
3. 解析器按文件类型提取正文、页码、标题、段落和基础 metadata。
4. Chunker 按配置生成带 overlap、token_count、content_hash、page_no 和 section 的 Chunk。
5. Embedding Provider 调用真实 Embedding API，为每个 Chunk 生成向量。
6. PostgreSQL 写入 Chunk 真值和 ChunkAccessFilter。
7. Milvus upsert 向量和过滤字段。
8. OpenSearch upsert 文本、metadata 和过滤字段。
9. LLM API 抽取实体关系后写入 Neo4j Entity、Relation、ChunkRef。
10. IndexSyncJob 和 IngestJob 分阶段记录成功、失败、耗时和错误摘要。

### 4.2 数据边界

PostgreSQL 保存 Chunk 正文、版本、权限和状态真值。Milvus、OpenSearch 和 Neo4j 只保存可重建副本或图谱索引，不作为最终 Evidence 真值。

## 5. V1.5 设计

### 5.1 QA 流程

1. P09 创建 QARun，锁定 ConfigRevision 和 overrideParams。
2. Query Rewrite 调用真实 LLM API。
3. Embedding API 生成 query 向量。
4. Dense Retrieval 查询 Milvus，Sparse Retrieval 查询 OpenSearch，Graph Retrieval 查询 Neo4j。
5. 所有候选按 chunk_id 回表 PostgreSQL，并按当前用户权限裁剪。
6. Fusion/Rerank 合并候选并输出诊断摘要。
7. Generation 调用真实 LLM API，只使用授权 Evidence。
8. Citation Builder 根据 PostgreSQL Chunk、DocumentVersion 和 metadata 构建引用。
9. Trace 保存每个阶段的输入输出摘要、耗时、错误和降级状态。

### 5.2 回放流程

1. P10 从历史 QARun 获取回放上下文。
2. 回放上下文包含 query、sourceRunId、configRevisionId、overrideParams、retrieval channels、topK、temperature、graphSnapshotId 和原诊断摘要。
3. P09 带上下文复跑，创建新的 QARun。
4. P10 对比原 run 和新 run 的状态、答案、证据、引用、Trace 指标和配置差异。
5. 历史 Evidence 读取和复跑都按当前权限重新校验。

## 6. 验证策略

- Sprint 19：验证真实解析、Chunk 切分和 LLM/Embedding API 契约。
- Sprint 20：验证 Milvus、OpenSearch、Neo4j 真实写入和 IndexSyncJob 状态。
- Sprint 21：验证 P09 真实 Dense/Sparse/Graph/LLM 链路。
- Sprint 22：验证 P10 回放复跑、结果对比和权限回归。

## 7. 风险

- 真实文件格式解析容易扩张，首轮只覆盖 txt、md、pdf、docx。
- 外部依赖不可用会影响端到端验收，脚本需要区分“代码能力缺失”和“环境不可用”。
- LLM API 输出不稳定，图谱抽取和生成必须记录模型配置和响应摘要，避免不可复盘。
- 回放如果复用历史授权结果会产生泄露风险，必须只复用上下文并重新鉴权。
