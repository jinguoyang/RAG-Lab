# 多视图 ChunkRevision 与分块策略设计规范

> 用途：本文件是 B-320 / Sprint 65 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

将当前固定长度分块升级为可版本化、多视图的 ChunkRevision 能力，支持固定、标题、语义、父子、表格感知等分块策略，为不同 RAG 场景选择合适上下文粒度。

## 范围

- 新增 `chunkRevisionId`、`chunkViewType`、`chunkStrategy`、`sourceBlockRange` 等元数据。
- 支持按知识库或文档创建新的分块版本。
- 首批策略：fixed、heading、semantic、parent_child、table_aware。
- 分块结果可独立重建检索索引，不覆盖历史正式版本。

## 不做

- 不在本任务实现所有策略的最优算法。
- 不删除历史 chunk。
- 不把分块策略暴露成无限自由参数。

## 设计要点

- 分块输入应优先来自 ParsedDocumentV2，缺失时兼容旧文本。
- heading 分块使用标题层级和段落边界。
- semantic 分块可以先实现为段落聚合加 embedding 断点，后续再增强。
- parent_child 分块同时生成小块和父级上下文块。
- table_aware 分块保留表格整体与行列上下文。

## 开发注意项点

- 同一文档允许多个 chunk revision 共存，检索时必须明确使用哪一个。
- 重新分块必须记录发起人、时间、策略参数和来源 parseVersion。
- 分块不得破坏权限继承关系。

## 验收标准

- API 支持创建和查询分块版本。
- 至少 fixed 与 heading 策略有真实输出差异。
- chunk 可追溯到 ParsedDocumentV2 block range。
- 检索链路可以选择指定 chunk revision。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_chunk_revision_strategy.py -q
python -m pytest backend/app/tests/integration/test_rechunk_revision_indexing.py -q
python -m compileall backend/app
git diff --check
```
