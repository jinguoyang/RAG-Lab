# 迭代计划 Sprint 65

## 1. Sprint 基本信息

- Sprint 名称：Sprint 65
- Sprint 主题：多视图分块与 Contextual Chunking
- 涉及 Epic：E34 高质量 RAG 核心优化
- 建议版本：V2.3
- 时间范围：待排期
- 目标：在 ParsedDocumentV2 基础上建立可版本化、多视图分块能力，并引入 LLM 辅助 contextual chunk 元数据。

## 2. 关键假设

- Sprint 64 已提供统一解析结果和 provenance。
- 分块版本是检索索引的来源，不应直接覆盖历史正式分块。
- LLM 生成的 contextual metadata 是辅助字段，不是引用证据正文。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-320 | 多视图 ChunkRevision 与分块策略 | P0 | 3d | Ready | [Spec](../../specs/2026-05-30-rag-multiview-chunking-spec.md) |
| B-321 | Contextual Chunking 与 Late Chunking 预留 | P1 | 2d | Ready | [Spec](../../specs/2026-05-30-rag-contextual-chunking-late-chunking-spec.md) |

## 4. 验收标准

- 同一文档支持多个 chunk revision 共存。
- fixed、heading、parent_child 等分块策略至少有可验证差异。
- contextual metadata 可异步生成、缓存并进入检索 trace。
- 原始引用仍指向 chunk 原文和 provenance。

## 5. 范围边界

- 不立即接入特定 late chunking 模型。
- 不实现复杂图谱摘要。
- 不删除历史 chunk 数据。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/unit/test_chunk_revision_strategy.py backend/app/tests/unit/test_contextual_chunking_cache.py -q
python -m pytest backend/app/tests/integration/test_rechunk_revision_indexing.py backend/app/tests/integration/test_contextual_chunking_job.py -q
python -m compileall backend/app
git diff --check
```

## 7. 关联文档

- [高质量 RAG 核心优化实施计划](../../plans/2026-05-30-high-quality-rag-core-optimization-plan.md)
- [多视图 ChunkRevision 规范](../../specs/2026-05-30-rag-multiview-chunking-spec.md)
- [Contextual Chunking 规范](../../specs/2026-05-30-rag-contextual-chunking-late-chunking-spec.md)

## 8. 执行记录

- 待执行。
