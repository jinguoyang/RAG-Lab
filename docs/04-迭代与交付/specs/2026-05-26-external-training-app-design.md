# 外部培训应用设计规范

> 本文是 E33 员工培训 Agent 与外部培训应用深化的设计规范，属于后续实现的活文档。外部培训应用是接入平台的轻量 demo 应用，不具备 LLM、RAG、Agent 决策或评分模型能力。

## 1. 目标

外部培训应用用于验证平台员工培训 Agent 的真实接入方式：

- 管理人员在外部培训应用中审核学习计划和题库草稿。
- 员工在外部培训应用中上课、提问和答题。
- 外部培训应用将审核结果、课堂事件和答题事件提交给平台。
- 平台返回结构化课堂输出，外部培训应用只负责渲染和本地记录。

## 2. 关键边界

外部培训应用必须保持简单：

- 不调用 LLM。
- 不访问向量库、图数据库、OpenSearch 或平台内部 RAG Provider。
- 不保存文档正文、Chunk 正文、Prompt、RAG Trace 或 LLM 原始响应。
- 不自行决定课堂业务状态流转。
- 不实现完整 LMS、证书、班级或组织学习档案。

外部培训应用可以保存：

- 外部用户。
- 平台 App 绑定配置。
- 审核任务和审核操作记录。
- 课堂会话与消息展示记录。
- 答题 UI 状态和提交记录。

## 3. 最小页面

### 3.1 平台绑定页

配置平台地址、App ID 和 API Key 引用。API Key 只用于服务端调用平台，不在浏览器端展示。

### 3.2 学习计划审核页

展示平台生成的结构化学习计划草稿：

- 岗位名称和岗位描述摘要。
- 能力组。
- 推荐文档。
- 证据摘要。
- 推荐原因。
- 阅读顺序。

审核人可调整顺序、删除不相关文档、提交通过或驳回。

### 3.3 题库审核页

展示平台生成的结构化题目草稿：

- 题型。
- 题干。
- 选项。
- 标准答案。
- 解析。
- rubric。
- 来源证据。

认证题必须审核通过后才能使用。

### 3.4 员工课堂页

提供最小上课体验：

- 多轮对话框。
- 当前课程内容。
- 当前学习状态。
- 平台返回的 `uiActions` 渲染区域。
- A/B/C/D 单选题组件。
- 判断题和主观题基础输入。

## 4. 数据库设计

外部培训应用使用独立数据库。首版建议使用 SQLite 或 PostgreSQL 均可，字段保持迁移友好。

### 4.1 `external_users`

保存外部培训应用自己的用户。

- `id`
- `display_name`
- `employee_no`
- `role`
- `created_at`

### 4.2 `platform_app_bindings`

保存外部培训应用与平台 RAG App 的绑定。

- `id`
- `platform_base_url`
- `platform_app_id`
- `platform_api_key_ref`
- `status`
- `created_at`

### 4.3 `training_review_tasks`

保存学习计划和题库审核任务的本地记录。

- `id`
- `platform_draft_id`
- `platform_plan_id`
- `review_type`
- `status`
- `reviewer_id`
- `submitted_payload`
- `reviewed_at`
- `created_at`

### 4.4 `training_class_sessions`

保存本地课堂会话与平台课堂会话的映射。

- `id`
- `external_user_id`
- `platform_session_id`
- `platform_plan_id`
- `current_state`
- `last_event_at`
- `created_at`

### 4.5 `training_class_messages`

保存课堂消息展示记录。

- `id`
- `session_id`
- `role`
- `content`
- `platform_message_id`
- `ui_actions_json`
- `created_at`

### 4.6 `training_answer_records`

保存本地答题提交记录。

- `id`
- `session_id`
- `platform_question_id`
- `question_type`
- `selected_answer`
- `submitted_payload`
- `score`
- `created_at`

## 5. 接入方式

外部培训应用后端调用平台 API：

- 拉取或生成学习计划草稿。
- 提交学习计划审核结果。
- 拉取或生成题库草稿。
- 提交题库审核结果。
- 创建课堂会话。
- 提交课堂事件。
- 提交答题事件。

外部培训应用前端不直接调用平台 LLM/RAG 接口，只调用本应用后端。

## 6. 验收标准

- 外部培训应用可独立启动并初始化数据库。
- 审核页面能展示、编辑和提交结构化学习计划。
- 题库页面能展示、编辑和提交结构化题目。
- 课堂页面能渲染平台返回的结构化 `uiActions`。
- 单选题以 A/B/C/D 组件完成答题交互。
- 应用代码中不存在 LLM Provider、Embedding Provider 或直接模型调用配置。
