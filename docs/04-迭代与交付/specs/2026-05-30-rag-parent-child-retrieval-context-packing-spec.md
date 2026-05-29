# 大小 Chunk / Parent-child 检索与上下文打包设计规范

> 用途：本文件是 B-323 / Sprint 66 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

实现“小 Chunk 精准检索 + 大 Chunk 连贯上下文”的 parent-child 检索和上下文打包能力，解决命中片段太碎、答案上下文不足和引用不连续的问题。

## 范围

- 小块用于召回和 rerank，大块或父块用于生成上下文。
- `chunkWindow` 支持按同文档相邻块扩展。
- `packingStrategy` 支持 relevance_first、document_order、section_grouped。
- 上下文打包输出保留小块命中证据和父块扩展来源。

## 不做

- 不在本任务处理图谱多跳。
- 不把所有相邻块无条件塞入上下文。
- 不取消 token 预算限制。

## 设计要点

- 检索命中小块后，通过 parent id、section id 或 block range 找到父级上下文。
- 打包时优先保留高相关证据，再补充必要邻近上下文。
- 引用应指向原始命中块或明确的父块范围，不能只引用拼接后的上下文。

## 开发注意项点

- 相邻扩展必须受 token 预算和文档权限限制。
- 同一父块被多个小块命中时要去重。
- trace 需要区分 retrieved evidence 与 expanded context。

## 验收标准

- 父子分块知识库中，小块命中能带出父级上下文。
- 不同 `packingStrategy` 产生可解释的上下文顺序差异。
- 引用仍能定位到页码、段落或 block。
- token 预算生效，超预算内容被截断并记录。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_parent_child_context_packing.py -q
python -m pytest backend/app/tests/integration/test_parent_child_retrieval.py -q
python -m compileall backend/app
git diff --check
```
