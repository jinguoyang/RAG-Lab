# V1.6 / V1.7 真实 RAG 闭环与模块化调优设计

## 1. 背景

V1.4 已补齐真实文档入库与多副本构建，V1.5 已补齐真实检索、生成、引用和回放复跑。但这些能力仍更像分段验收：解析、索引、检索、回放各自有验证入口，缺少一条以真实文档为起点、以可复盘 QA 结果为终点的完整 RAG 验收链路。

V1.6 的重点是把真实 RAG 功能完全走通，证明系统能基于文档完成一次真实有效的解析、检索查询、监控诊断和回放复跑。V1.7 再在这个稳定主链路上深化 RAG 模块化，让配置中心逐步贴近真实 RAG 优化流程。

## 2. V1.6 设计目标

- 使用真实样例文档完成上传、解析、Chunk 切分和 metadata 落库。
- 将同一批 Chunk 同步到 Milvus、OpenSearch 和 Neo4j，或在依赖不可用时记录可复测的环境限制。
- 基于该文档完成一次真实 QA 查询，候选必须回表 PostgreSQL 并执行当前权限裁剪。
- Answer 必须基于授权 Evidence 生成，Citation 必须能定位到文档、版本、页码或章节和 Chunk。
- P05/P06/P07/P09/P10 展示解析、索引、检索、生成、引用和回放阶段的状态、耗时和失败原因。
- P10 支持对真实 QA Run 回放复跑，并比较答案、Evidence、Citation、Trace 和配置差异。
- 新增 V1.6 端到端验收脚本，输出通过、代码缺口或环境限制三类结果。

## 3. V1.6 非目标

- 不扩展新的 RAG 调参节点；节点模块化放入 V1.7。
- 不建设公网聊天、多轮会话记忆或复杂实验平台。
- 不引入新的外部组件选型。
- 不允许真实链路失败时退回 mock/local 并标记成功。

## 4. V1.6 数据流

1. P06 上传 `docs/examples/` 中的真实文档。
2. 后端创建 Document、DocumentVersion、IngestJob，并保存原始文件。
3. 解析器生成真实 Chunk、页码或章节、token 数、parser metadata 和 content hash。
4. Embedding Provider 生成向量，IndexSyncJob 分别写入 Milvus、OpenSearch 和 Neo4j。
5. P09 创建 QARun，锁定 ConfigRevision 和 overrideParams。
6. Query Rewrite、Dense、Sparse、Graph、Fusion、Rerank、Permission Filter、Generation 和 Citation 依次写入 Trace。
7. P10 读取历史 QARun，回放到 P09，复跑后生成新的 QARun。
8. P10 对比原运行和复跑运行的答案、Evidence、Citation、Trace 和配置差异。

## 5. V1.7 设计目标

- 扩展受控 RAG 节点：Query Rewrite、Multi Query、Dense Retrieval、Sparse Retrieval、Hybrid Fusion、Graph Retrieval、Rerank、Context Packing。
- 丰富节点参数：topK、scoreThreshold、fusionWeight、rerankTopN、maxContextTokens、chunkWindow、metadataFilter、graphDepth、graphExpansionLimit。
- 保存每次 QARun 的 Pipeline Snapshot 和节点级参数快照。
- 支持用 EvaluationRun 对比两个配置版本的命中、引用、答案质量、耗时和失败原因。
- P08 从静态模板页演进为可复核 RAG Pipeline 调参台；P10 展示配置效果差异和优化建议。

## 6. V1.7 非目标

- 不开放任意 Python、HTTP 工具节点或自由 DAG。
- 不建设完整 Prompt 管理平台。
- 不自动上线优化建议；所有建议都必须由用户复核后再保存或激活。
- 不改变 PostgreSQL 作为业务真值中心的原则。

## 7. 验证策略

- Sprint 23：验证真实文档从上传到 QA Answer 的主链路。
- Sprint 24：验证监控诊断、回放复跑、差异对比和 V1.6 端到端脚本。
- Sprint 25：验证受控 RAG 节点参数保存、校验和执行生效。
- Sprint 26：验证 Pipeline Snapshot、评估对比和优化建议闭环。

## 8. 风险

- 外部 Provider 环境不可用会阻塞真实端到端验收，脚本必须区分代码缺口和环境限制。
- 文档格式差异会扩大解析范围，V1.6 只承诺使用既有样例文档完成主链路。
- V1.7 如果一次开放过多节点，P08 会滑向通用编排器；必须保持受控节点和受控参数。
- Pipeline 参数如果没有快照，会导致回放和评估无法解释结果差异。
