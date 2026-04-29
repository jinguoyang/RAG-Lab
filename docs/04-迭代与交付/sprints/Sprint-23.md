# 迭代计划 Sprint 23

## 1. Sprint 基本信息

- Sprint 名称：Sprint 23
- Sprint 主题：真实文档 RAG 端到端链路
- 涉及 Epic：E20 真实 RAG 有效闭环
- 建议版本：V1.6
- 时间范围：待定
- 目标：基于真实样例文档打通上传、解析、Chunk、索引副本、QA 查询、授权 Evidence 和 Citation 的端到端路径。

## 2. 关键假设

- V1.4/V1.5 已具备真实解析、索引、检索、生成和回放的模块能力。
- V1.6 优先验证真实链路是否能串起来，不在本 Sprint 扩展新的 RAG 调参节点。
- 外部 Provider 不可用时必须记录环境限制，不能把 mock 成功当作真实验收。

## 3. 本 Sprint 目标

- 选定 `docs/examples/` 中的真实文档作为 V1.6 smoke 样例。
- 建立上传后解析、Chunk、Embedding、Milvus、OpenSearch、Neo4j 的一键验收路径。
- 建立基于该文档的 QA 查询和授权 Evidence 生成路径。
- 统一记录解析、索引、检索、生成阶段的诊断摘要。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S23-001 | B-101 | 建立真实文档样例集和端到端 smoke 数据 | P0 | 0.5d | Codex | Todo |
| S23-002 | B-102 | 打通上传后解析、Chunk、索引副本的一键验收路径 | P0 | 2d | Codex | Todo |
| S23-003 | B-103 | 打通基于真实文档的 QA 查询与授权 Evidence 生成 | P0 | 2d | Codex | Todo |
| S23-004 | B-104 | 完善解析、索引、检索、生成阶段的统一监控诊断 | P0 | 1.5d | Codex | Todo |

## 5. 验收标准

- 上传真实样例文档后，P07 能看到真实 Chunk 内容、页码或章节、token 数和 parser metadata。
- 同一批 Chunk 能从 PostgreSQL 追溯到 Milvus、OpenSearch 和 Neo4j 副本，或明确记录对应 Provider 环境不可用。
- P09 能基于该文档返回答案、Evidence 和 Citation，不允许使用 mock/fallback 冒充成功。
- Trace 至少覆盖 parse、embedding、denseRetrieval、sparseRetrieval、graphRetrieval、fusion、rerank、permissionFilter、generation、citation。

## 6. 范围边界

- 不新增 V1.7 的 Pipeline 节点和参数配置。
- 不要求一次覆盖所有真实文档格式；优先使用已存在样例文档。
- 不以历史运行结果代替本 Sprint 的新 QA Run 验收。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Sprint 23 验证脚本：`conda run -n rag-lab python scripts/verify_v16_real_rag_e2e.py --stage ingest-query`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`

## 8. 执行记录

- V1.6 smoke 初始结果：`conda run -n rag-lab python scripts\verify_v16_real_rag_e2e.py` 输出 `V16CodeGap`；首个缺口为真实样例文档解析后 Chunk 缺少页码或章节定位信息。终端输出包含 `ERROR conda.cli.main_run:execute(125)`。
