# 迭代计划 Sprint 51

## 1. Sprint 基本信息

- Sprint 名称：Sprint 51
- Sprint 主题：语义检索 + LLM 测验生成
- 涉及 Epic：E32 场景化智能应用
- 建议版本：V2.2
- 时间范围：待排期
- 目标：将 retrieve 接口从 ILIKE 文本匹配升级为 Milvus 向量语义检索，将培训测验和讲解生成从硬编码模板替换为 LLM 驱动的智能出题与结构化讲解。

## 2. 关键假设

- Sprint 47 至 Sprint 50 已完成两个场景的主要功能。
- Milvus、Embedding Provider 和 LLM Provider 基础设施已就绪。
- 本 Sprint 不涉及前端改动，仅后端能力增强。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-259 | retrieve 接口改造为 Milvus 向量语义检索（含 ILIKE 回退） | P0 | 2d | Done |
| B-260 | LLM 驱动的培训测验生成（含模板回退） | P0 | 2d | Done |
| B-261 | LLM 驱动的培训讲解结构化输出（含文本分割回退） | P0 | 1.5d | Done |
| B-262 | 语义检索和 LLM 生成的单元测试与边界覆盖 | P1 | 1d | Done |

## 4. 验收标准

- `retrieve` 接口在 `dense_retrieval_provider=milvus` 时使用向量语义检索，返回按相关性排序的结果。
- `retrieve` 接口在 `dense_retrieval_provider=local` 或向量检索失败时回退到 ILIKE。
- 培训测验题目由 LLM 基于真实培训内容生成，干扰选项有合理性。
- 培训讲解由 LLM 提炼为结构化要点，而非简单文本分割。
- 所有新代码有对应单元测试，10 个测试全部通过。

## 5. 范围边界

- 不涉及多轮对话上下文（属于 Sprint 52）。
- 不涉及前端 UI 改动。
- 不涉及自适应培训难度（属于 Sprint 52）。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python -m pytest app/tests/unit/test_semantic_retrieve.py -v
conda run -n rag-lab python -m pytest app/tests/unit/test_llm_quiz_generation.py -v
conda run -n rag-lab python -m pytest app/tests/unit/test_llm_explain_generation.py -v
```

## 7. 关联文档

- [语义检索 + LLM 测验生成实现计划](../../plans/2026-05-25-sprint51-semantic-search-llm-quiz.md)

## 8. 执行记录

- 新增 `_build_provider_set()` 辅助函数，延迟导入避免循环依赖。
- `retrieve_app_runtime_evidence` 改造为双路径：向量检索（Milvus）+ ILIKE 回退，向量路径失败时静默回退。
- 新增 `_generate_quiz_with_llm()` 函数，调用 LLM 生成结构化测验题目，失败时返回 None。
- `_build_training_quiz` 改为优先调用 LLM，回退到模板。
- 新增 `_generate_explain_with_llm()` 函数，调用 LLM 提炼培训讲解要点，失败时返回 None。
- `_build_structured_output` 的 `training_explain` 分支改为优先 LLM，回退到文本分割。
- 新增 10 个单元测试，覆盖向量检索、ILIKE 回退、空 query、空结果、LLM quiz 生成、LLM explain 生成和模板回退。
