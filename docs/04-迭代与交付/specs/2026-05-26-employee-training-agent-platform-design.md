# 员工培训 Agent 平台侧设计规范

> 本文是 E33 员工培训 Agent 与外部培训应用深化的设计规范，属于后续实现的活文档。平台侧负责 RAG、Agent、多轮教学、状态机、结构化生成、评分和权威业务数据；外部培训应用只通过平台 API 接入。

## 1. 目标

在现有 E32 场景化智能应用基座上，将员工培训助手从演示能力升级为可复用的平台 Agent 能力：

- 根据岗位和岗位描述，基于知识库文档生成结构化学习计划草稿。
- 将 AI 草稿校验、归一化并保存为平台自己的业务数据。
- 支持学习计划、题库和课堂流程的人工审核结果回写。
- 提供平台侧课堂状态机、多轮教学对话、受控答疑和结构化课堂事件。
- 保证所有 Agent 输出可追溯到 RAG 证据、计划版本、题库版本和课堂会话。

## 2. 责任边界

平台侧负责：

- RAG 检索、Evidence、Citation、权限裁剪和 QARun 回溯。
- LLM 调用、Agent 提示词、结构化草稿生成和结构化课堂输出。
- 学习计划、题库、课堂会话、状态机和评分结果的权威数据。
- 对外提供 API，供外部培训应用展示、审核和提交课堂事件。

平台侧不负责：

- 外部培训应用的业务页面、员工门户、组织学习档案或证书 UI。
- 外部培训应用自己的用户表、页面路由和本地操作记录。
- 将嵌入页作为正式培训系统前端；现有嵌入页只作为接入演示保留。

## 3. 结构化数据原则

AI 只生成结构化草稿，不能直接作为业务真值。所有草稿必须经过程序处理：

1. Schema 校验：字段、枚举、数组长度、必填项和类型必须合法。
2. 权限校验：引用文档、Chunk 和知识库必须属于当前 App 可访问范围。
3. 归一化：程序生成稳定 ID、排序、状态、版本号和审计字段。
4. 落库：保存为平台业务表中的计划、章节、文档引用、题目和课堂事件。
5. 审核：外部培训应用提交审核结果后，平台再次校验并冻结可执行版本。

## 4. 核心能力

### 4.1 学习计划生成

输入岗位名称、岗位描述、知识库和可选约束，平台调用 RAG 检索候选文档，再由 Agent 输出结构化草稿。

草稿最小字段：

- `jobTitle`
- `jobDescriptionSummary`
- `abilityGroups`
- `documents`
- `evidenceChunkIds`
- `recommendReason`
- `readingOrder`

平台保存为学习计划草稿，审核通过后冻结为可执行计划版本。

### 4.2 题库生成与审核

平台基于已审核学习计划生成题目草稿。题目分为：

- `practice`：课堂练习题，可用于教学过程。
- `certification`：认证题，必须人工审核通过后才能使用。

首版题型：

- `single_choice`
- `true_false`
- `subjective`

主观题必须包含 `rubric`。AI 辅助评分只能依据 rubric 输出分数、理由和风险标记。

### 4.3 课堂状态机

平台侧状态机是权威状态机。外部培训应用只能提交事件，不能自行推进业务状态。

首版状态：

- `INIT`
- `PLAN`
- `TEACH`
- `CHECK_UNDERSTAND`
- `QUIZ`
- `GRADE`
- `REVIEW`
- `SUMMARY`
- `NEXT_SECTION`
- `COMPLETED`
- `OFF_TOPIC`

AI 可以建议下一步，但程序必须判断是否允许流转。

### 4.4 多轮教学与受控答疑

平台保留课堂会话历史，并将必要上下文注入 Agent 生成链路。答疑边界首版规则：

- 只回答当前学习计划内、当前文档或已学文档范围内的问题。
- 无可靠证据时拒答。
- 偏离课程目标时进入 `OFF_TOPIC`。
- 回答必须返回证据摘要或 Citation。

### 4.5 结构化课堂输出

平台返回课堂输出时，应包含可见内容和 UI 动作描述：

- `visibleContent`
- `classroomState`
- `uiActions`
- `citations`
- `control`
- `progressUpdate`

单选题必须作为结构化 `uiActions` 返回，由外部培训应用渲染为 A/B/C/D 交互组件。

## 5. 接口草案

- `POST /api/v1/training/plans/drafts`
- `POST /api/v1/training/plans/{draftId}/review`
- `POST /api/v1/training/questions/drafts`
- `POST /api/v1/training/questions/{draftId}/review`
- `POST /api/v1/training/classroom/sessions`
- `POST /api/v1/training/classroom/sessions/{sessionId}/events`
- `GET /api/v1/training/classroom/sessions/{sessionId}`

接口字段统一使用 `camelCase`，数据库字段统一使用 `snake_case`。

## 6. 验收标准

- AI 学习计划草稿不能绕过程序校验直接发布。
- 未审核学习计划不能创建课堂会话。
- 未审核认证题不能进入认证流程。
- 平台状态机能拒绝非法流转。
- 多轮课堂答疑能使用历史上下文，并仍受当前学习计划证据范围约束。
- 单选题以结构化动作返回，外部培训应用无需解析自然语言题目。
