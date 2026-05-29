# 迭代计划 Sprint 63

## 1. Sprint 基本信息

- Sprint 名称：Sprint 63
- Sprint 主题：RAG 配置真实生效与关键 no-op 修复
- 涉及 Epic：E34 高质量 RAG 核心优化
- 建议版本：V2.3
- 时间范围：待排期
- 目标：建立 RAG 节点配置生效审计口径，并优先修复多查询、RRF、生成参数和 App Runtime 检索链路中的关键弱生效问题。

## 2. 关键假设

- P08 配置中心和默认 Pipeline 已存在，但部分配置项未真正影响后端执行。
- 本 Sprint 先解决“配置是否生效可被证明”的问题，再进入文档解析和检索质量深化。
- 权限过滤仍是最终安全门禁，任何修复不得绕过授权证据过滤。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-316 | RAG 节点配置真实生效审计与可视化标识 | P0 | 2d | Ready | [Spec](../../specs/2026-05-30-rag-config-effectiveness-audit-spec.md) |
| B-317 | RAG 关键配置真实执行修复 | P0 | 3d | Ready | [Spec](../../specs/2026-05-30-rag-config-runtime-fix-spec.md) |

## 4. 验收标准

- 所有默认 RAG 节点配置项都有生效状态说明。
- QA Run trace 能展示实际命中的配置项和被忽略配置项。
- Multi Query、RRF、`maxOutputTokens` 和 App Runtime evidence retrieve 的关键问题得到修复或明确降级。
- 前端配置中心不会把未生效配置展示成已生效。

## 5. 范围边界

- 不实现高质量文档解析。
- 不实现多跳图谱和 Corrective RAG。
- 不替换现有 QA Run Pipeline 架构。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/unit/test_rag_config_effectiveness.py backend/app/tests/unit/test_multi_query_generation.py backend/app/tests/unit/test_rag_fusion_rrf.py -q
python -m pytest backend/app/tests/integration/test_qa_run_trace.py backend/app/tests/integration/test_app_runtime_retrieval.py -q
cd frontend
npm run build
cd ..
git diff --check
```

## 7. 关联文档

- [高质量 RAG 核心优化实施计划](../../plans/2026-05-30-high-quality-rag-core-optimization-plan.md)
- [配置真实生效审计规范](../../specs/2026-05-30-rag-config-effectiveness-audit-spec.md)
- [关键配置真实执行修复规范](../../specs/2026-05-30-rag-config-runtime-fix-spec.md)

## 8. 执行记录

- 待执行。
