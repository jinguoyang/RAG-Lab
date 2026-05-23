# 迭代计划 Sprint 47

## 1. Sprint 基本信息

- Sprint 名称：Sprint 47
- Sprint 主题：场景模板与智能应用模型基线
- 涉及 Epic：E32 场景化智能应用
- 建议版本：V2.1
- 时间范围：待排期
- 目标：建立知识库问答助手和员工培训助手的后端模板、应用元数据和 P13 场景识别基础。

## 2. 关键假设

- 现有 RAG App、App Runtime、QARun、Citation 和反馈回流链路保持可用。
- 第一版场景模板采用后端内置配置，不建设模板 CRUD。
- 第一版只支持单知识库绑定，避免引入多知识库权限合并和检索路由。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-241 | 新增内置 Agent 场景模板查询接口 | P0 | 1d | Done |
| B-242 | 扩展 RAG App 场景元数据和 DTO 兼容策略 | P0 | 1.5d | Done |
| B-243 | 实现场景推荐 Pipeline / ConfigRevision 创建能力 | P0 | 2d | Done |
| B-244 | P13 列表和详情展示场景类型、发布渠道和嵌入状态 | P1 | 1.5d | Done |

## 4. 验收标准

- `GET /api/v1/agent-scenario-templates` 返回知识库问答助手和员工培训助手两个模板。
- 创建 RAG App 时可保存 `scenarioType`、`scenarioTemplateId`、`scenarioConfig`、`publishChannels` 和 `embedSettings`。
- 旧应用缺少场景 metadata 时按知识库问答助手兼容展示。
- 可为场景应用创建专属 `saved` ConfigRevision，且不改变知识库 active revision。
- P13 应用列表和详情能展示场景类型和发布状态。

## 5. 范围边界

- 不实现完整场景创建向导。
- 不实现嵌入页和短期 Token。
- 不实现培训测验和评分。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests/unit/test_agent_scenario_templates.py -q
conda run -n rag-lab pytest app/tests/unit/test_rag_app_scenario_metadata.py -q
conda run -n rag-lab pytest app/tests/unit/test_scenario_recommended_revision.py -q
```

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

```powershell
git diff --check
```

## 7. 关联文档

- [场景化智能应用开发计划](../../plans/2026-05-24-agent-scenario-apps.md)

## 8. 实际结果

- 新增内置 Agent 场景模板查询接口，返回知识库问答助手和员工培训助手两个模板。
- RAG App DTO 和 metadata 支持场景类型、模板、参数、发布渠道和嵌入设置，旧应用默认兼容为知识库问答助手。
- 创建 RAG App 时可按场景生成专属 `saved` ConfigRevision，且不改变知识库 active revision。
- P13 应用列表和详情可展示场景类型、发布方式、嵌入状态和场景模板。

## 9. 实际验证

```powershell
cd backend
& 'C:\Users\crrcd\.conda\envs\rag-lab\python.exe' -m pytest app/tests/unit/test_agent_scenario_templates.py app/tests/unit/test_rag_app_scenario_metadata.py app/tests/unit/test_scenario_recommended_revision.py -q
& 'C:\Users\crrcd\.conda\envs\rag-lab\python.exe' -m compileall app
```

```powershell
cd frontend
npm run lint
npm run test -- src/app/adapters/ragAppAdapter.test.ts
npm run build
```

```powershell
git diff --check
```
