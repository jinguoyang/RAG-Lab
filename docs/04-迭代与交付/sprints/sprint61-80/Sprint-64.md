# 迭代计划 Sprint 64

## 1. Sprint 基本信息

- Sprint 名称：Sprint 64
- Sprint 主题：文档高保真解析与 ParsedDocumentV2
- 涉及 Epic：E34 高质量 RAG 核心优化
- 建议版本：V2.3
- 时间范围：待排期
- 目标：建立文档解析 Provider 路由和 ParsedDocumentV2 契约，为后续分块、引用、表格和流程图能力提供可靠证据底座。

## 2. 关键假设

- Sprint 63 已明确节点配置真实生效口径。
- 文档解析输出必须先统一，再谈分块和检索优化。
- 历史文档不强制立即迁移，可通过重新解析任务升级。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-318 | 高质量文档解析 Provider 路由 | P0 | 2d | Ready | [Spec](../../specs/2026-05-30-rag-parser-routing-document-intelligence-spec.md) |
| B-319 | ParsedDocumentV2 与证据定位 Provenance | P0 | 3d | Ready | [Spec](../../specs/2026-05-30-rag-parsed-document-v2-provenance-spec.md) |

## 4. 验收标准

- 文档解析能按策略选择 Provider 并记录解析质量状态。
- ParsedDocumentV2 能保存页、块、表格和块级 provenance。
- chunk 或引用能关联到解析 block 或 block range。
- 基础解析 fallback 不影响现有上传入库流程。

## 5. 范围边界

- 不绑定唯一外部解析服务。
- 不实现完整表格问答。
- 不在本 Sprint 做检索融合算法升级。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/unit/test_document_parser_routing.py backend/app/tests/unit/test_parsed_document_v2_schema.py -q
python -m pytest backend/app/tests/integration/test_document_parse_fallback.py backend/app/tests/integration/test_parsed_document_provenance.py -q
python -m compileall backend/app
git diff --check
```

## 7. 关联文档

- [高质量 RAG 核心优化实施计划](../../plans/2026-05-30-high-quality-rag-core-optimization-plan.md)
- [文档解析 Provider 路由规范](../../specs/2026-05-30-rag-parser-routing-document-intelligence-spec.md)
- [ParsedDocumentV2 规范](../../specs/2026-05-30-rag-parsed-document-v2-provenance-spec.md)

## 8. 执行记录

- 待执行。
