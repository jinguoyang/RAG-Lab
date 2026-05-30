# 高质量 RAG E2E 真实评测 Runner 实施计划

> 用途：本文件是 `2026-05-30-high-quality-rag-core-optimization-plan.md` 的窄切片执行计划，仅覆盖 B-327 中“真实 QA 评测不再默认阻塞”的最小闭环。

## 目标

将 `backend/scripts/evaluate_high_quality_rag.py` 的默认真实评测模式从 `NotImplementedError` 改为可调用真实 QA Run 链路；显式 `--allow-mock` 仍保留为脚本结构检查模式。

## 关键假设

- 真实评测通过现有 QA Run HTTP API 接入，不新增数据库表或新 Provider。
- 未配置知识库 ID 或后端不可达时，应给出明确错误，不回退到模拟指标。
- 本切片不声明 E34 完成，也不更新 B-316 到 B-327 为 Done。

## 修改范围

- `backend/scripts/evaluate_high_quality_rag.py`：新增 HTTP QA Runner、真实结果指标计算和 CLI 参数。
- `backend/app/tests/e2e/test_high_quality_rag_acceptance.py`：新增真实 Runner 注入测试与缺配置失败测试。

## 不修改范围

- 不实现 Graph/RAPTOR 真实 Neo4j 多跳。
- 不实现高质量 OCR/Layout Parser。
- 不新增结构化证据持久化表。
- 不回填产品待办或 Sprint 状态为 Done。

## 验证方式

1. `python -m pytest backend/app/tests/e2e/test_high_quality_rag_acceptance.py -q`
2. `python backend/scripts/evaluate_high_quality_rag.py --allow-mock`
3. `python backend/scripts/evaluate_high_quality_rag.py` 应在未配置真实参数时给出明确配置错误，而不是 `NotImplementedError` 或模拟通过。

## 真实复测命令

使用命令行参数：

```powershell
python backend/scripts/evaluate_high_quality_rag.py `
  --kb-id <knowledge_base_id> `
  --api-base-url http://127.0.0.1:8000/api/v1 `
  --dev-user admin `
  --fixture backend/app/tests/fixtures/high_quality_rag_evaluation_fixture.json
```

或使用环境变量：

```powershell
$env:RAG_LAB_EVAL_KB_ID="<knowledge_base_id>"
$env:RAG_LAB_EVAL_API_BASE_URL="http://127.0.0.1:8000/api/v1"
$env:RAG_LAB_EVAL_DEV_USER="admin"
python backend/scripts/evaluate_high_quality_rag.py --fixture backend/app/tests/fixtures/high_quality_rag_evaluation_fixture.json
```

如需绑定特定配置版本，可追加 `--config-revision-id <config_revision_id>` 或设置 `RAG_LAB_EVAL_CONFIG_REVISION_ID`。
