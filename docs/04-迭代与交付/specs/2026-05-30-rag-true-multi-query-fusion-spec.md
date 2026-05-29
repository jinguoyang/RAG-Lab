# 真 Multi Query、RRF/MMR 与融合可解释设计规范

> 用途：本文件是 B-322 / Sprint 66 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

将检索从单次查询扩展为可控的多查询检索，并支持 RRF、MMR 和融合解释，提升召回率、排序稳定性和可调试性。

## 范围

- LLM 或规则生成多条查询：原始问题、同义改写、关键词化查询、约束拆解查询。
- dense、sparse、graph 等 provider 按多查询并发或顺序检索。
- 实现 RRF 融合、MMR 去冗余和来源权重融合。
- trace 展示每个候选来自哪些 query、哪些 provider、原始排名和最终得分。

## 不做

- 不让模型自由调用任意检索工具。
- 不实现无限制查询扩展。
- 不改变权限过滤最终门禁。

## 设计要点

- `queryCount` 是上限，不是必须生成的固定数量。
- RRF 适合跨 provider 排名融合，MMR 适合减少上下文冗余，两者应可组合。
- query 生成失败时回退到原始 query。

## 开发注意项点

- 多查询会增加成本和延迟，需要记录每个 provider 调用耗时。
- 候选去重应优先按 chunk id，其次按 source block 或文本 hash。
- 融合算法单元测试要使用固定候选集，避免依赖外部服务。

## 验收标准

- `queryCount` 增大时，候选来源中能看到多条查询。
- RRF/MMR 配置改变时最终排序和 trace 可解释。
- 权限过滤后不会返回未授权候选。
- 多查询失败不会导致单查询不可用。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_query_expansion.py -q
python -m pytest backend/app/tests/unit/test_rag_fusion_mmr_rrf.py -q
python -m pytest backend/app/tests/integration/test_multi_query_hybrid_retrieval.py -q
python -m compileall backend/app
git diff --check
```
