# 迭代计划 Sprint 68

## 1. Sprint 基本信息

- Sprint 名称：Sprint 68
- Sprint 主题：多跳推理、引用校验与高质量 RAG 验收
- 涉及 Epic：E34 高质量 RAG 核心优化
- 建议版本：V2.3
- 时间范围：待排期
- 目标：增强 Graph/RAPTOR 多跳与长文档聚合能力，并通过 Answer/Citation Verifier 与 E2E 评测集形成质量闭环。

## 2. 关键假设

- Sprint 67 已提供结构化证据和 Corrective RAG 控制器。
- 图谱和摘要索引是可重建副本，不替代 PostgreSQL 业务真值。
- 高质量 RAG 必须用评测集证明收益，而不是只增加节点。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-326 | Graph 多跳与 RAPTOR 层级摘要 | P1 | 3d | Ready | [Spec](../../specs/2026-05-30-rag-graph-multihop-raptor-spec.md) |
| B-327 | Answer/Citation Verifier 与高质量 RAG E2E 验收 | P0 | 3d | Ready | [Verifier Spec](../../specs/2026-05-30-rag-answer-citation-verifier-spec.md)、[E2E Spec](../../specs/2026-05-30-rag-quality-e2e-acceptance-spec.md) |

## 4. 验收标准

- Graph 多跳检索能返回路径解释和对应原文证据。
- RAPTOR 或层级摘要命中后仍能引用原文块。
- Answer/Citation Verifier 能拒绝无证据、错引或越权答案。
- E2E 评测报告覆盖普通问答、表格问答、多跳问答和权限隔离。

## 5. 范围边界

- 不把离线评测结果等同于线上满意度。
- 不让摘要替代原文引用。
- 不引入无法复现的人工主观评分作为唯一验收标准。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/unit/test_graph_multihop_retrieval.py backend/app/tests/unit/test_answer_citation_verifier.py -q
python -m pytest backend/app/tests/integration/test_graph_raptor_rag.py backend/app/tests/integration/test_verified_rag_answer.py -q
python -m pytest backend/app/tests/e2e/test_high_quality_rag_acceptance.py -q
python -m compileall backend/app
git diff --check
```

## 7. 关联文档

- [高质量 RAG 核心优化实施计划](../../plans/2026-05-30-high-quality-rag-core-optimization-plan.md)
- [Graph 多跳与 RAPTOR 规范](../../specs/2026-05-30-rag-graph-multihop-raptor-spec.md)
- [Answer/Citation Verifier 规范](../../specs/2026-05-30-rag-answer-citation-verifier-spec.md)
- [高质量 RAG E2E 验收规范](../../specs/2026-05-30-rag-quality-e2e-acceptance-spec.md)

## 8. 执行记录

- 2026-06-02 B-326/B-327 收口：
  - `graph_retrieval_multihop()` 增加可选 `graph_provider` 参数，有 Provider 时委托真实图查询。
  - 新增 `test_graph_raptor_rag.py`（9 个集成测试）和 `test_verified_rag_answer.py`（11 个集成测试）。
  - 扩充 E2E 评测 fixture 至 10 条样本，覆盖 faq、citation、permission_isolation、multi_hop、table、long_document、cross_document。
  - 全量验证通过：37 单元 + 20 集成 + 18 E2E = 75 测试。
