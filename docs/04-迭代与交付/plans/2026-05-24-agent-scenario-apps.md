# 场景化智能应用开发计划

> 本计划用于记录“知识库问答助手”和“员工培训助手”两个典型场景的长期开发安排。执行时应按 Sprint 拆分推进，完成后回写产品待办清单和 Sprint 总览。

**目标：** 在现有文档库、知识库、智能应用三层模型上，新增场景化智能应用能力，让平台用户通过场景向导快速创建知识库问答助手和员工培训助手，并通过 API 与嵌入页对外使用。

**架构：** 不另起新的 Agent 平台，继续复用 `rag_apps`、`config_revisions`、`qa_runs`、`app_runtime`、Citation、反馈和调用审计。场景模板第一版采用后端内置配置，应用场景参数落入 `rag_apps.metadata.scenario`，对外运行仍回溯到 QARun。

**技术栈：** FastAPI、PostgreSQL、React、Vite、TypeScript、Radix UI、现有 RAG Provider 与 App Runtime。

---

## 1. 范围边界

### 1.1 本期实现

- 内置两个场景模板：知识库问答助手、员工培训助手。
- P13 升级为“智能应用管理”，新增场景向导。
- 支持 API 调用和短期 Token 嵌入页。
- 知识库问答助手支持对话、Citation、无证据策略、反馈回流。
- 员工培训助手支持讲解、测验生成、答题评分、错题解释和训练结果记录。
- 新增运行时结构化输出接口、检索接口、培训答题接口和训练报告接口。
- 补齐后端单元测试、Runtime 集成测试、前端构建和核心 E2E 验收。

### 1.2 本期不做

- 不做自由工作流 Agent 或多工具自主执行。
- 不做多知识库组合检索。
- 不做完整 LMS，包括班级、课程体系、考试证书和组织级学习档案。
- 不允许外部请求传入主体级权限过滤条件。
- 不在浏览器或嵌入页暴露 App API Key。

## 2. 数据与接口设计

### 2.1 应用元数据

第一版不新增 `rag_apps` 表字段，使用现有 JSON 字段承载场景信息。

```json
{
  "scenario": {
    "scenarioType": "knowledge_qa",
    "scenarioTemplateId": "builtin_knowledge_qa_v1",
    "scenarioConfig": {
      "answerLength": "standard",
      "citationCount": 3,
      "noEvidencePolicy": "refuse",
      "showSuggestedQuestions": true,
      "greeting": "你好，我可以基于当前知识库回答问题。"
    },
    "publishChannels": {
      "api": true,
      "embed": true
    },
    "embedSettings": {
      "enabled": true,
      "allowedOrigins": ["https://example.com"],
      "theme": "light",
      "greeting": "你好，我是知识库问答助手。"
    }
  }
}
```

员工培训助手使用同一结构，`scenarioType` 为 `employee_training`，`scenarioConfig` 增加 `audience`、`defaultTopic`、`difficulty`、`questionCount`、`passingScore` 和 `recordTrainingResult`。

### 2.2 新增和扩展接口

| 接口 | 说明 | 验证重点 |
| --- | --- | --- |
| `GET /api/v1/agent-scenario-templates` | 读取内置场景模板和配置字段 | 返回两个模板，字段稳定 |
| `POST /api/v1/app-runtime/embed-tokens` | 通过 App API Key 生成短期嵌入 Token | 过期、篡改、跨 App 调用被拒绝 |
| `POST /api/v1/app-runtime/retrieve` | 只检索授权证据，不生成答案 | 只返回授权 Citation 摘要 |
| `POST /api/v1/app-runtime/structured-runs` | 生成结构化回答、培训讲解或测验 | 输出可解析 JSON，并写入 QARun |
| `POST /api/v1/app-runtime/training/quiz-submissions` | 提交培训测验答案并评分 | 写入训练结果和错题解释 |
| `GET /api/v1/rag-apps/{appId}/training-report` | 管理端查看培训结果聚合 | 仅应用管理员可访问 |
| `POST /api/v1/app-runtime/chat-messages` | 扩展支持 Embed Token 和场景参数 | 旧 App API Key 调用保持兼容 |

## 3. Sprint 拆分

| Sprint | 主题 | Backlog | 交付结果 |
| --- | --- | --- | --- |
| Sprint 47 | 场景模板与应用模型 | B-241 至 B-244 | 后端可创建带场景元数据的智能应用，P13 列表和详情可识别场景类型 |
| Sprint 48 | 场景向导与知识问答助手 | B-245 至 B-249 | 用户可通过向导创建知识库问答助手，并通过 API 与嵌入页试运行 |
| Sprint 49 | 员工培训助手运行时 | B-250 至 B-254 | 培训讲解、测验生成、答题评分、错题解释和训练结果记录闭环 |
| Sprint 50 | 验收硬化与文档同步 | B-255 至 B-258 | 端到端验收、权限回归、文档同步和发布说明完成 |

## 4. 分阶段实施任务

### Task 1: 场景模板后端基线

**涉及文件：**

- 新增：`backend/app/services/agent_scenario_template_service.py`
- 新增：`backend/app/schemas/agent_scenario.py`
- 新增：`backend/app/api/routes/agent_scenarios.py`
- 修改：`backend/app/api/router.py`
- 测试：`backend/app/tests/unit/test_agent_scenario_templates.py`

- [ ] 定义 `AgentScenarioTemplateDTO`、字段配置 DTO 和两个内置模板。
- [ ] 增加模板查询服务，固定返回 `knowledge_qa` 和 `employee_training`。
- [ ] 增加路由 `GET /api/v1/agent-scenario-templates`。
- [ ] 单元测试覆盖模板数量、模板 ID、默认参数和字段配置。
- [ ] 运行 `conda run -n rag-lab pytest app/tests/unit/test_agent_scenario_templates.py -q`。

### Task 2: RAG App 场景元数据扩展

**涉及文件：**

- 修改：`backend/app/schemas/rag_app.py`
- 修改：`backend/app/services/rag_app_service.py`
- 修改：`frontend/src/app/types/ragApp.ts`
- 修改：`frontend/src/app/adapters/ragAppAdapter.ts`
- 测试：`backend/app/tests/unit/test_rag_app_scenario_metadata.py`

- [ ] 为 `RagAppDTO`、创建请求和更新请求增加场景字段。
- [ ] 保存时将场景字段写入 `metadata.scenario`，读取时从 metadata 提升为 DTO 字段。
- [ ] 旧应用缺少 scenario 时默认视为 `knowledge_qa`。
- [ ] 前端类型和 Adapter 增加场景标签、发布渠道和嵌入状态展示字段。
- [ ] 单元测试覆盖创建、更新、旧数据兼容。

### Task 3: 场景推荐配置版本

**涉及文件：**

- 修改：`backend/app/services/default_pipeline.py`
- 修改：`backend/app/services/config_service.py`
- 修改：`backend/app/services/rag_app_service.py`
- 测试：`backend/app/tests/unit/test_scenario_recommended_revision.py`

- [ ] 新增按场景构造推荐 Pipeline 的函数。
- [ ] 知识问答模板保持严格 Citation 和无证据拒答。
- [ ] 培训模板增加教学式 generation 参数和结构化输出提示参数。
- [ ] 创建场景应用时可选择创建 App 专属 `saved` Revision。
- [ ] 确认该 Revision 不改变知识库 active revision。

### Task 4: P13 场景向导

**涉及文件：**

- 修改：`frontend/src/app/pages/P13_RagAppManagement.tsx`
- 新增：`frontend/src/app/services/agentScenarioService.ts`
- 新增：`frontend/src/app/types/agentScenario.ts`
- 测试：前端单元测试或 Playwright 场景创建用例

- [ ] 将创建入口改为“创建场景助手”。
- [ ] 实现六步向导：选择场景、选择知识库、选择运行配置、配置参数、发布方式、预览创建。
- [ ] 向导首版只允许单知识库。
- [ ] 对知识问答和员工培训展示不同参数表单。
- [ ] 创建成功后进入对应应用详情，并展示场景配置。
- [ ] 运行 `cd frontend; npm run lint; npm run test; npm run build`。

### Task 5: 嵌入 Token 和嵌入页

**涉及文件：**

- 修改：`backend/app/schemas/app_runtime.py`
- 修改：`backend/app/services/app_runtime_service.py`
- 修改：`backend/app/api/routes/app_runtime.py`
- 新增：`frontend/src/app/pages/P20_EmbeddedRuntime.tsx`
- 修改：`frontend/src/app/routes.tsx`
- 测试：`backend/app/tests/unit/test_app_runtime_embed_token.py`

- [ ] 增加短期 Token 签发和校验逻辑。
- [ ] `chat-messages` 支持 App API Key 和 Embed Token 两种鉴权。
- [ ] 嵌入页不保存或展示 App API Key。
- [ ] 嵌入页根据场景类型渲染问答或培训界面。
- [ ] Token 过期、签名篡改、跨 App 使用返回稳定错误。

### Task 6: 知识问答助手运行能力

**涉及文件：**

- 修改：`backend/app/services/app_runtime_service.py`
- 修改：`frontend/src/app/pages/P13_RagAppManagement.tsx`
- 修改：`frontend/src/app/pages/P20_EmbeddedRuntime.tsx`
- 测试：`backend/app/tests/integration/test_knowledge_qa_scenario_runtime.py`

- [ ] `chat-messages` 将问答场景参数写入 QARun override。
- [ ] 增加 `retrieve` 接口，只返回授权证据摘要。
- [ ] P13 试运行区展示问答结果、Citation 和反馈入口。
- [ ] 嵌入页支持问答、引用卡片和反馈按钮。
- [ ] 集成测试覆盖入库、创建应用、Runtime 问答、Citation、反馈回流。

### Task 7: 员工培训助手运行能力

**涉及文件：**

- 修改：`backend/app/schemas/app_runtime.py`
- 修改：`backend/app/services/app_runtime_service.py`
- 修改：`backend/app/api/routes/app_runtime.py`
- 修改：`frontend/src/app/pages/P13_RagAppManagement.tsx`
- 修改：`frontend/src/app/pages/P20_EmbeddedRuntime.tsx`
- 测试：`backend/app/tests/integration/test_employee_training_scenario_runtime.py`

- [ ] 增加 `structured-runs` 支持 `training_explain` 和 `training_quiz_generate`。
- [ ] 增加 `training/quiz-submissions` 支持答题评分和错题解释。
- [ ] 训练结果写入 `app_messages.metadata.trainingResult`。
- [ ] P13 和嵌入页支持讲解、测验、提交答案和报告展示。
- [ ] 集成测试覆盖讲解、测验、评分、错题解释和 QARun 回溯。

### Task 8: 培训报告与验收硬化

**涉及文件：**

- 修改：`backend/app/services/rag_app_service.py`
- 修改：`backend/app/api/routes/rag_apps.py`
- 修改：`frontend/src/app/services/ragAppService.ts`
- 修改：`frontend/src/app/pages/P13_RagAppManagement.tsx`
- 文档：系统设计、接口设计、数据模型、产品待办和 Sprint 记录

- [ ] 增加应用级培训报告接口。
- [ ] P13 详情增加训练结果摘要。
- [ ] 建立 Playwright 主链路验收：创建两个场景应用、试运行、反馈、训练报告。
- [ ] 运行后端编译、相关 pytest、前端 lint/test/build 和 `git diff --check`。
- [ ] 回填 Sprint 47-50 执行结果和产品待办状态。

## 5. 验证命令

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests/unit/test_agent_scenario_templates.py -q
conda run -n rag-lab pytest app/tests/unit/test_rag_app_scenario_metadata.py -q
conda run -n rag-lab pytest app/tests/unit/test_app_runtime_embed_token.py -q
conda run -n rag-lab pytest app/tests/integration/test_knowledge_qa_scenario_runtime.py -q
conda run -n rag-lab pytest app/tests/integration/test_employee_training_scenario_runtime.py -q
```

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run lint
npm run test
npm run build
```

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab
git diff --check
```

## 6. 完成标准

- 两个场景模板可被查询、创建和管理。
- 新旧 RAG App 均可正常运行，旧应用无场景 metadata 时兼容为知识问答助手。
- 知识库问答助手支持 API、嵌入页、Citation 和反馈。
- 员工培训助手支持讲解、测验、评分、错题解释和训练结果摘要。
- 所有 Runtime 输出仍能追溯到 QARun、ConfigRevision、Evidence 和 Citation。
- 外部调用不暴露 API Key、系统提示词、未授权 Chunk 正文或完整内部 Trace。
