# 迭代计划 Sprint 48

## 1. Sprint 基本信息

- Sprint 名称：Sprint 48
- Sprint 主题：场景向导与知识库问答助手
- 涉及 Epic：E32 场景化智能应用
- 建议版本：V2.1
- 时间范围：待排期
- 目标：让平台用户通过场景向导创建知识库问答助手，并通过 API 与嵌入页完成问答、Citation 和反馈闭环。

## 2. 关键假设

- Sprint 47 已完成场景模板、场景元数据和推荐配置版本能力。
- 嵌入页不暴露 App API Key，必须使用短期 Embed Token。
- 知识库问答助手继续复用现有 QARun 和 Citation 安全边界。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-245 | P13 新增场景助手创建向导 | P0 | 2d | Ready |
| B-246 | 实现 App Runtime 短期 Embed Token | P0 | 2d | Ready |
| B-247 | 新增嵌入式运行页基础框架 | P0 | 2d | Ready |
| B-248 | 实现知识问答助手 API 与嵌入页问答体验 | P0 | 2d | Ready |
| B-249 | 新增 Runtime retrieve 接口用于只检索授权证据 | P1 | 1.5d | Ready |

## 4. 验收标准

- P13 可通过向导创建知识库问答助手。
- 向导包含选择场景、选择知识库、选择运行配置、配置参数、发布方式和预览创建。
- App API Key 可生成短期 Embed Token。
- 嵌入页可使用 Embed Token 完成对话，不暴露 App API Key。
- 问答结果展示 Citation，并可提交反馈。
- `retrieve` 接口只返回授权证据摘要，不返回完整 Trace 或未授权 Chunk 正文。

## 5. 范围边界

- 不实现员工培训助手测验流程。
- 不实现多知识库应用。
- 不实现外部 JS SDK。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests/unit/test_app_runtime_embed_token.py -q
conda run -n rag-lab pytest app/tests/integration/test_knowledge_qa_scenario_runtime.py -q
```

```powershell
cd frontend
npm run lint
npm run test
npm run build
npx playwright test
```

```powershell
git diff --check
```

## 7. 关联文档

- [场景化智能应用开发计划](../../plans/2026-05-24-agent-scenario-apps.md)
