# 迭代计划 Sprint 53

## 1. Sprint 基本信息

- Sprint 名称：Sprint 53
- Sprint 主题：嵌入页体验 + 运营视图
- 涉及 Epic：E32 场景化智能应用
- 建议版本：V2.2
- 时间范围：待排期
- 目标：为嵌入页添加流式输出（SSE）和 Markdown 渲染，提升对话体验；为管理端添加调用分析和反馈闭环视图。

## 2. 关键假设

- Sprint 51 已完成语义检索和 LLM 测验生成。
- Sprint 52 已完成多轮对话和自适应培训。
- 嵌入页已支持消息列表模式。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-269 | 后端 `chat-messages` 端点支持 `responseMode=streaming`（SSE） | P0 | 2d | Todo |
| B-270 | 后端 SSE 流式推送实现 | P0 | 1.5d | Todo |
| B-271 | 前端嵌入页 SSE 客户端实现 | P0 | 2d | Todo |
| B-272 | 前端嵌入页 Markdown 渲染（react-markdown） | P1 | 1d | Todo |
| B-273 | P13 调用统计与反馈分析标签页 | P1 | 2d | Todo |
| B-274 | P13 反馈分析展示（满意率、趋势图、高频问题） | P2 | 1.5d | Todo |

## 4. 验收标准

- 嵌入页问答支持流式输出，逐 token 显示回答。
- 回答内容支持 Markdown 格式渲染（标题、列表、代码块等）。
- P13 管理端可查看调用统计（总数、趋势、平均响应时间）。
- P13 管理端可查看反馈分析（满意率、高频问题）。
- 所有新代码有对应单元测试。

## 5. 范围边界

- 不涉及多知识库检索。
- 不涉及自适应培训（属于 Sprint 52）。
- 不涉及运营告警或自动扩缩容。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python -m pytest app/tests/unit/test_streaming_chat.py -v
conda run -n rag-lab python -m pytest app/tests/unit/test_app_analytics.py -v
```

```powershell
cd frontend
npm run build
```

## 7. 关联文档

- [嵌入页体验 + 运营视图实现计划](../../plans/2026-05-25-sprint53-embedded-ux-analytics.md)

## 8. 执行记录

- 待执行。
