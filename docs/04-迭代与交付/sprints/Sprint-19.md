# 迭代计划 Sprint 19

## 1. Sprint 基本信息

- Sprint 名称：Sprint 19
- Sprint 主题：真实解析与 Chunk 入库
- 涉及 Epic：E18 真实入库与多副本构建
- 建议版本：V1.4
- 时间范围：待定
- 目标：替换上传后的占位解析链路，让真实文件能解析为可追溯 Chunk，并接入真实 LLM/Embedding API 契约。

## 2. 关键假设

- 本 Sprint 优先支持 txt、md、pdf、docx 四类文件。
- PostgreSQL 仍是 Chunk 正文、页码、章节、hash、密级和状态的业务真值中心。
- 真实 LLM API 采用 OpenAI-compatible Chat Completion 契约，Embedding API 采用 OpenAI-compatible Embedding 契约。
- 解析失败必须明确失败，不再用占位 Chunk 冒充成功。

## 3. 本 Sprint 目标

- 引入真实解析器，保留文件格式、页码、章节和解析器版本信息。
- 升级 Chunk 切分策略，支持 chunk size、overlap 和结构化 metadata。
- 固化真实 LLM API 与 Embedding API 的配置、诊断和错误处理边界。
- 为后续 Milvus、OpenSearch、Neo4j 写入准备统一 Chunk payload。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S19-001 | B-081 | 引入真实文档解析器并替换占位 Chunk | P0 | 2d | Codex | Todo |
| S19-002 | B-082 | 升级 Chunk 切分策略和结构化元数据 | P0 | 1.5d | Codex | Todo |
| S19-003 | B-083 | 接入真实 LLM API 和 Embedding API 契约 | P0 | 1.5d | Codex | Todo |
| S19-004 | B-084 | 为 Chunk 生成真实 Embedding 并标准化向量 Payload | P0 | 1.5d | Codex | Todo |

## 5. 验收标准

- 上传 txt、md、pdf、docx 样例后，能在 P07 看到真实 Chunk 内容、页码或章节、token 数和 parser metadata。
- 不支持格式或解析失败时，DocumentVersion 和 IngestJob 状态为 failed，错误原因可见。
- Embedding API 连接失败、鉴权失败和响应格式错误能进入作业错误摘要。
- Chunk payload 可同时支撑 Milvus、OpenSearch 和 Neo4j 后续写入。

## 6. 范围边界

- 不在本 Sprint 完成 Milvus、OpenSearch、Neo4j 的真实写入。
- 不实现复杂版面还原或 OCR。
- 不建设 Prompt 管理平台。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- V1.4 入库脚本：`conda run -n rag-lab python scripts/verify_sprint19_real_parse.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`
