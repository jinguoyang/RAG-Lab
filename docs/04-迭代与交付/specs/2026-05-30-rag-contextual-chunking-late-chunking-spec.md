# Contextual Chunking 与 Late Chunking 设计规范

> 用途：本文件是 B-321 / Sprint 65 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

引入 LLM 辅助的 contextual chunk 摘要和 late chunking 预处理能力，提升单个 chunk 的自解释能力，同时保留长文档上下文和后续 embedding 优化空间。

## 范围

- 为 chunk 增加 `contextualSummary`、`sectionPath`、`documentBrief`、`generationMeta`。
- 后台任务按文档 hash、chunk revision、prompt version 和模型版本生成 contextual metadata。
- 支持失败回退：无摘要时仍使用原始 chunk。
- 为 late chunking 保存文档级 embedding 或长上下文处理的扩展字段和接口边界。

## 不做

- 不要求立即接入特定 late chunking 模型。
- 不让 LLM 改写原始证据文本。
- 不在前台请求中同步生成大量摘要。

## 设计要点

- contextual summary 是检索辅助字段，不是引用证据正文。
- 生成结果必须可缓存、可重放、可按 prompt 版本失效。
- 下游检索可选择将原文、标题路径和 summary 共同用于 embedding 或 sparse 字段。

## 开发注意项点

- 摘要生成需要记录 token、耗时、模型和失败原因。
- LLM 输出不能包含未出现在文档中的定位信息。
- 对敏感知识库要遵守现有 provider 调用安全边界。

## 验收标准

- 后台任务可为指定 chunk revision 生成 contextual metadata。
- 重复执行同一版本命中缓存，不重复调用 LLM。
- 检索 trace 能说明是否使用 contextual 字段。
- 原始引用仍指向 chunk 原文和 provenance。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_contextual_chunking_cache.py -q
python -m pytest backend/app/tests/integration/test_contextual_chunking_job.py -q
python -m compileall backend/app
git diff --check
```
