# Agentic / Corrective RAG 重检索控制器设计规范

> 用途：本文件是 B-325 / Sprint 67 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

在最终回答前引入受控的证据质量判断和重检索机制。当证据不足、冲突或覆盖问题不完整时，控制器可以改写查询、补充检索或拒答，而不是直接生成低可信答案。

## 范围

- 定义证据充分性评分：覆盖度、相关性、冲突、权限状态、引用可定位性。
- 支持最多两轮纠错动作：rewrite_query、expand_scope、retrieve_structured、ask_clarification、answer_insufficient。
- 所有动作进入 trace，并可由配置开启或关闭。
- 证据不足时输出“资料不足”或澄清问题。

## 不做

- 不实现开放式自主 Agent。
- 不允许控制器越权访问知识库。
- 不让模型自行决定调用未注册工具。

## 设计要点

- 控制器应位于 rerank/context packing 之后、generation 之前。
- 判断可以先用规则加 LLM 评分混合实现。
- 每轮重检索必须继承原始权限过滤和用户上下文。

## 开发注意项点

- 最大迭代次数、动作白名单和超时必须硬编码或受控配置。
- 对成本敏感场景默认关闭 LLM 评分，只使用规则阈值。
- trace 要能解释为什么重检索、使用了哪些新查询、是否接受新证据。

## 验收标准

- 证据为空或低分时不会强行生成答案。
- 证据不足但可补检时，会执行一次受控重检索。
- 达到最大迭代次数后停止，并输出可解释结果。
- 所有重检索动作遵守权限过滤。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_corrective_rag_controller.py -q
python -m pytest backend/app/tests/integration/test_corrective_rag_runtime.py -q
python -m compileall backend/app
git diff --check
```
