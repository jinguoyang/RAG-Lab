# 迭代计划 Sprint 52

## 1. Sprint 基本信息

- Sprint 名称：Sprint 52
- Sprint 主题：多轮对话 + 自适应培训
- 涉及 Epic：E32 场景化智能应用
- 建议版本：V2.2
- 时间范围：待排期
- 目标：为知识库问答助手添加多轮对话上下文，使 LLM 能理解追问和指代；为员工培训助手添加自适应难度和知识掌握度追踪。

## 2. 关键假设

- Sprint 51 已完成语义检索和 LLM 测验生成。
- 嵌入页已支持基本问答和培训交互。
- 本 Sprint 不涉及流式输出（属于 Sprint 53）。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-263 | 多轮对话上下文注入（`_read_conversation_history`） | P0 | 1.5d | Todo |
| B-264 | `generate_answer` 支持 `chat_history` 参数 | P0 | 1d | Todo |
| B-265 | `chat_with_app_runtime` 注入历史消息 + 前端消息列表 | P0 | 2d | Todo |
| B-266 | 知识点掌握度追踪（`_extract_topic_mastery`） | P0 | 1.5d | Todo |
| B-267 | 测验评分后写入掌握度 + 培训报告知识点聚合 | P1 | 1.5d | Todo |
| B-268 | 前端培训报告知识点掌握度进度条展示 | P1 | 1d | Todo |

## 4. 验收标准

- 问答助手支持多轮对话，能理解追问和指代。
- 前端嵌入页展示完整对话历史，而非单条回答。
- 培训测验评分后自动提取知识点掌握度。
- 培训报告按知识点维度展示掌握度进度条。
- 所有新代码有对应单元测试。

## 5. 范围边界

- 不涉及流式输出（属于 Sprint 53）。
- 不涉及多知识库检索。
- 不涉及运营分析视图（属于 Sprint 53）。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python -m pytest app/tests/unit/test_multi_turn_chat.py -v
conda run -n rag-lab python -m pytest app/tests/unit/test_adaptive_training.py -v
```

```powershell
cd frontend
npm run build
```

## 7. 关联文档

- [多轮对话 + 自适应培训实现计划](../../plans/2026-05-25-sprint52-multi-turn-adaptive-training.md)

## 8. 执行记录

- 待执行。
