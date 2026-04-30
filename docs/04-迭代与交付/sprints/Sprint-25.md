# 迭代计划 Sprint 25

## 1. Sprint 基本信息

- Sprint 名称：Sprint 25
- Sprint 主题：RAG 检索节点模块化配置
- 涉及 Epic：E21 RAG 模块化调优
- 建议版本：V1.7
- 时间范围：待定
- 目标：在 V1.6 真实链路跑通后，扩展受控 Pipeline 节点和节点参数，让 P08 更贴近真实 RAG 调参流程。

## 2. 关键假设

- V1.6 已提供可回放、可复测的真实 RAG 主链路。
- V1.7 只开放受控 RAG 节点，不开放任意代码或 HTTP 工具节点。
- 参数配置必须能映射到后端执行契约和 QARun 快照。

## 3. 本 Sprint 目标

- 扩展 Query Rewrite、Multi Query、Dense、Sparse、Hybrid Fusion、Graph Retrieval、Rerank 和 Context Packing 的配置模型。
- P08 能保存、校验和展示这些节点的核心参数。
- 后端执行链路能读取新增参数，但保持 PostgreSQL 业务真值和权限裁剪边界不变。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S25-001 | B-109 | 扩展 Pipeline 节点模型支持 Query Rewrite、Multi Query 和 Context Packing | P0 | 2d | Codex | Todo |
| S25-002 | B-110 | 丰富 Dense、Sparse、Hybrid 检索节点参数 | P0 | 2d | Codex | Todo |
| S25-003 | B-111 | 丰富 Graph Retrieval 节点参数和扩展策略 | P1 | 1.5d | Codex | Todo |
| S25-004 | B-112 | 丰富 Fusion、Rerank 策略和诊断指标 | P0 | 1.5d | Codex | Todo |
| S25-005 | B-113 | 支持上下文组装策略参数和引用约束 | P0 | 1.5d | Codex | Todo |
| S25-006 | B-114 | 将 P08 升级为可复核 RAG Pipeline 调参台 | P0 | 2d | Codex | Todo |

## 5. 验收标准

- P08 能配置并保存每类受控 RAG 节点的核心参数。
- Pipeline 校验能阻止无效参数组合，例如所有检索节点均关闭、topK 非法或 context token 超限。
- QARun 执行时能读取配置参数，并在 Trace 中展示实际使用值。
- 前端构建通过，旧配置仍可读取。

## 6. 范围边界

- 不开放任意 DAG、任意脚本节点或外部工具调用。
- 不建设 Prompt 管理平台。
- 不要求 V1.7 第一轮完成评估对比和优化建议展示。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Pipeline 参数验证：`conda run -n rag-lab python scripts/verify_v17_pipeline_params.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`
