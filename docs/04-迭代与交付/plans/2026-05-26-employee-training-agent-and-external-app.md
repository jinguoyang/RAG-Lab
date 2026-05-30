# 员工培训 Agent 与外部培训应用实施计划

> 本计划是 E33 的开发计划，承接 [员工培训 Agent 平台侧设计规范](../specs/2026-05-26-employee-training-agent-platform-design.md) 和 [外部培训应用设计规范](../specs/2026-05-26-external-training-app-design.md)。Sprint 47-51 保留为 E32 场景化智能应用基座；Sprint 52-53 按本计划重排。
>
> 2026-05-30 收口说明：本文作为历史计划和执行依据保留；当前 Backlog 与 Sprint 状态以 `docs/04-迭代与交付/产品待办清单.md` 和 `docs/04-迭代与交付/sprints/README.md` 为准。Sprint 52-57 已完成收口，Sprint 58 仍处于 In Review，P2 长期规划继续保留 Todo。

**目标：** 将员工培训助手从演示型能力升级为平台可复用 Agent，并用一个无 LLM 能力的外部培训应用验证审核、上课和结构化答题接入。

**架构：** 平台侧负责 RAG、Agent、多轮对话、状态机、结构化生成、评分和权威业务数据；外部培训应用负责审核界面、课堂 UI、结构化答题组件和自己的最小数据库。外部培训应用只通过平台 API 接入，不直接调用 LLM 或 RAG Provider。

**技术栈：** FastAPI、PostgreSQL、SQLAlchemy、React、Vite、TypeScript；外部培训应用首版可使用轻量后端和 SQLite/PostgreSQL。

---

## 1. 与 Sprint 47-53 的关系

- Sprint 47-51：保留，作为场景化智能应用基座和演示能力。
- Sprint 52：由“多轮对话 + 自适应培训”调整为“平台课堂 Agent 基线”。
- Sprint 53：由“嵌入页体验 + 运营视图”调整为“外部培训应用基线”。
- 原 Sprint 52 的自适应培训、个人掌握度相关条目降为 P2 后续。
- 原 Sprint 53 的 SSE、Markdown、运营分析条目降为 P2 后续。

## 2. Sprint 拆分

| Sprint | 主题 | 交付重点 |
| --- | --- | --- |
| Sprint 52 | 平台课堂 Agent 基线 | 多轮对话、状态机、受控答疑、课堂事件 API |
| Sprint 53 | 外部培训应用基线 | 独立项目、数据库迁移、平台接入、学习计划审核 UI |
| Sprint 55 | 平台结构化学习计划 | 岗位描述生成学习计划、AI 草稿校验、平台业务数据落库 |
| Sprint 56 | 题库生成与审核 | 练习题/认证题草稿、人工审核、rubric、题库发布 |
| Sprint 57 | 外部培训应用课堂交互 | 课堂 UI、A/B/C/D 结构化答题、事件提交 |
| Sprint 58 | 端到端验收 | 计划生成、审核、上课、答题、追溯和文档同步 |

说明：Sprint 54 已用于 E31 mimo-v2.5 图片 Provider 硬化，因此 E33 的后续 Sprint 从 55 起延续。

## 3. Backlog 映射

### Sprint 52

- B-263：平台侧课堂多轮上下文管理。
- B-264：平台 Agent 生成链路支持课堂历史上下文。
- B-265：平台课堂事件注入历史并返回结构化课堂输出。
- B-280：平台侧课堂状态机。
- B-281：平台侧受控答疑与偏题处理。
- B-282：课堂结构化 `uiActions` 协议。

### Sprint 53

- B-283：外部培训应用项目骨架。
- B-284：外部培训应用数据库设计与迁移。
- B-285：外部培训应用平台绑定与 API 接入。
- B-286：外部培训应用学习计划审核页面。

### Sprint 55

- B-287：员工培训结构化学习计划生成。
- B-288：AI 学习计划草稿校验与程序数据转换。
- B-289：学习计划审核提交与版本快照。

### Sprint 56

- B-290：题库结构化草稿生成。
- B-291：认证题人工审核门禁。
- B-292：主观题 rubric 存储与 AI 辅助评分结构。

### Sprint 57

- B-293：外部培训应用题库审核页面。
- B-294：外部培训应用课堂页面。
- B-295：外部培训应用结构化答题组件。

### Sprint 58

- B-296：平台与外部培训应用端到端联调验收。
- B-297：同步接口设计、数据模型、数据库设计和 OpenAPI。

### 后续低优先级

- B-266 至 B-274：按原计划降级为 Deferred / P2。
- B-298 至 B-303：能力组复用、岗位级别、个人掌握度、题目多模态、错题复习、大文档细化配置。

## 4. 验证计划

每个 Sprint 至少执行：

```powershell
cd backend
conda run -n rag-lab python -m compileall app
```

涉及前端时执行：

```powershell
cd frontend
npm run build
```

外部培训应用 Sprint 需要补充独立验证：

```powershell
cd external-training-app
npm run build
```

文档调整执行：

```powershell
git diff --check
```

## 5. 完成标准

- Sprint 52/53 不再推进旧的自适应培训、SSE、Markdown 和运营分析计划。
- 平台侧课堂 Agent 能独立控制多轮对话、状态机和受控答疑。
- 外部培训应用能独立启动，并通过平台 API 完成审核与课堂最小链路。
- 外部培训应用没有 LLM、Embedding、RAG Provider 或模型调用配置。
- 长期规划进入低优先级 Backlog，不进入本轮开发。
