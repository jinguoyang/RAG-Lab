# 迭代计划 Sprint 21

## 1. Sprint 基本信息

- Sprint 名称：Sprint 21
- Sprint 主题：真实检索与生成链路
- 涉及 Epic：E19 真实检索与回放闭环
- 建议版本：V1.5
- 时间范围：待定
- 目标：让 P09 QA 调试基于真实 Milvus、OpenSearch、Neo4j、Rerank 和 LLM API 执行，不再依赖 local/mock 成功路径。

## 2. 关键假设

- V1.4 已完成真实入库，测试知识库中存在可用 Milvus、OpenSearch 和 Neo4j 副本。
- Dense、Sparse、Graph 任一路失败时可以 partial，但必须进入 Trace，不允许静默伪造成功。
- 所有候选进入生成前必须回表 PostgreSQL，并执行当前用户权限裁剪。
- 真实 LLM API 的 Query Rewrite 和 Generation 使用 Sprint 19 固化的 OpenAI-compatible 契约。

## 3. 本 Sprint 目标

- Dense 检索从 query embedding 到 Milvus search 再到 PostgreSQL 回表闭环。
- Sparse 检索从 OpenSearch BM25 到 PostgreSQL 回表闭环。
- Graph 检索从 Neo4j 实体/关系召回到 supporting chunk 回落闭环。
- Fusion、Rerank、Permission Filter、Generation 和 Citation 形成真实 Trace。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S21-001 | B-091 | 打通真实 Dense 检索闭环 | P0 | 1.5d | Codex | Todo |
| S21-002 | B-092 | 打通真实 Sparse 检索闭环 | P0 | 1.5d | Codex | Todo |
| S21-003 | B-093 | 打通真实 Graph 检索闭环 | P0 | 2d | Codex | Todo |
| S21-004 | B-094 | 完善真实候选 Fusion、Rerank 和诊断摘要 | P0 | 1.5d | Codex | Todo |
| S21-005 | B-095 | 使用真实 LLM API 完成 Query Rewrite 和 Generation | P0 | 1.5d | Codex | Todo |
| S21-006 | B-096 | 强化 Evidence 和 Citation 的来源定位 | P1 | 1d | Codex | Todo |

## 5. 验收标准

- P09 执行真实 QA 后，Trace 中能看到 queryRewrite、embedding、denseRetrieval、sparseRetrieval、graphRetrieval、fusion、rerank、permissionFilter、generation、citation。
- Dense/Sparse/Graph 候选均带有真实 chunk_id，且正文来自 PostgreSQL 回表结果。
- Answer 使用真实 LLM API 基于授权 Evidence 生成。
- Citation 可定位到文档、版本、页码、章节和 chunk。

## 6. 范围边界

- 不在本 Sprint 完成回放复跑和差异对比。
- 不建设多轮会话或公网聊天体验。
- 不允许跳过权限裁剪直接使用 Provider 返回正文。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Sprint 21 验证脚本：`conda run -n rag-lab python scripts/verify_sprint21_real_qa.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`
