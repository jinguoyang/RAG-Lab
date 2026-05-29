# RAG 关键配置真实执行修复设计规范

> 用途：本文件是 B-317 / Sprint 63 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

优先修复当前对 RAG 质量影响最大、且已经暴露在配置中心的关键配置项，使其从“可配置但弱生效”升级为“真实执行并可追踪”。

## 范围

- `multiQuery.queryCount` 真实生成多条查询，或在 Provider 不可用时明确降级。
- `fusion.method=rrf`、`rrfK` 和去重策略真实影响融合结果。
- `generation.maxOutputTokens` 传递到 LLM Provider 或被标记为不支持。
- App Runtime evidence retrieve 调用 provider 时补齐访问过滤参数，避免静默退回低质量检索。
- `contextPacking.chunkWindow` 最小实现为相邻 chunk 扩展，供 B-323 深化。

## 不做

- 不实现完整多跳图谱推理。
- 不实现复杂 agentic 纠错循环。
- 不新增商业文档解析 Provider。

## 设计要点

- 多查询生成应复用现有 LLM Provider，并保留原始 query。
- RRF 融合需要保留每个候选的来源列表、原始排名和最终排名解释。
- 对不支持 `maxOutputTokens` 的 provider，trace 必须说明参数被忽略。
- App Runtime 检索修复必须保持权限过滤为强制参数。

## 开发注意项点

- 不要为了修复一个参数而引入新的全局抽象层。
- 多查询失败时应回退到单查询，不应导致问答整体失败。
- RRF 和现有加权融合要可并存，便于 A/B 和回归。

## 验收标准

- 设置不同 `queryCount` 时，trace 中可看到实际执行的查询数量变化。
- `method=rrf` 与默认加权融合在同一候选集上产生可解释的不同排序。
- LLM 生成请求能体现 `maxOutputTokens` 的传递或不支持说明。
- App Runtime 在真实 provider 可用时不因参数缺失而退回 ILIKE。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_multi_query_generation.py -q
python -m pytest backend/app/tests/unit/test_rag_fusion_rrf.py -q
python -m pytest backend/app/tests/integration/test_app_runtime_retrieval.py -q
python -m compileall backend/app
git diff --check
```
