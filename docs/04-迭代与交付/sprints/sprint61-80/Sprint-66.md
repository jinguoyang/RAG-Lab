# 迭代计划 Sprint 66

## 1. Sprint 基本信息

- Sprint 名称：Sprint 66
- Sprint 主题：多查询融合与大小 Chunk 上下文
- 涉及 Epic：E34 高质量 RAG 核心优化
- 建议版本：V2.3
- 时间范围：待排期
- 目标：实现真正 Multi Query、RRF/MMR 融合和 parent-child 上下文打包，提升召回率、排序稳定性和生成上下文连贯性。

## 2. 关键假设

- Sprint 65 已提供可选择的多视图 chunk revision。
- 多查询和 parent-child 检索会增加成本和延迟，必须进入 trace。
- 权限过滤后再进入上下文打包，避免扩展出未授权内容。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-322 | 真 Multi Query、RRF/MMR 与融合可解释 | P0 | 3d | Ready | [Spec](../../specs/2026-05-30-rag-true-multi-query-fusion-spec.md) |
| B-323 | 大小 Chunk / Parent-child 检索与上下文打包 | P0 | 2d | Ready | [Spec](../../specs/2026-05-30-rag-parent-child-retrieval-context-packing-spec.md) |

## 4. 验收标准

- `queryCount` 改变会影响实际执行查询数量。
- RRF/MMR 改变最终排序并能解释来源。
- 小 Chunk 命中可扩展为父级上下文。
- trace 能区分 retrieved evidence 与 expanded context。

## 5. 范围边界

- 不实现 Corrective RAG 控制器。
- 不实现图谱多跳。
- 不取消现有加权融合，保留回退能力。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/unit/test_query_expansion.py backend/app/tests/unit/test_rag_fusion_mmr_rrf.py backend/app/tests/unit/test_parent_child_context_packing.py -q
python -m pytest backend/app/tests/integration/test_multi_query_hybrid_retrieval.py backend/app/tests/integration/test_parent_child_retrieval.py -q
python -m compileall backend/app
git diff --check
```

## 7. 关联文档

- [高质量 RAG 核心优化实施计划](../../plans/2026-05-30-high-quality-rag-core-optimization-plan.md)
- [Multi Query 与融合规范](../../specs/2026-05-30-rag-true-multi-query-fusion-spec.md)
- [Parent-child 检索规范](../../specs/2026-05-30-rag-parent-child-retrieval-context-packing-spec.md)

## 8. 执行记录

- 2026-06-02: B-322/B-323 运行时接入验证完成。
  - B-322: Multi Query + RRF/MMR 融合已接入 QA Run 运行时，支持 rrf、weighted、mmr 三种融合方法，trace 可解释来源。
  - B-323: chunkWindow 上下文扩展已接入 QA Run 运行时，支持相邻块扩展、父子检索和三种打包策略。
  - 测试证据: `test_rag_fusion_mmr_rrf.py`(13 用例)、`test_rag_fusion_rrf.py`(8 用例)、`test_multi_query_generation.py`(7 用例)、`test_parent_child_context_packing.py`(13 用例)、`test_qa_run_e34_runtime_chain.py`(4 用例)、`test_b322_b323_runtime_verification.py`(12 用例)。
  - 全部 57 个单元测试通过，B-322 和 B-323 状态置为 Done。
