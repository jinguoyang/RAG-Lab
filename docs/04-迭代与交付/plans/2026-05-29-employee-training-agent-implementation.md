# 员工培训 Agent 平台侧与应用侧实施计划

用途：本文件是 2026-05-29 员工培训 Agent 落地的执行计划与变更依据，作为历史归档保留。当前业务状态仍以 `docs/04-迭代与交付/产品待办清单.md` 等状态源为准。

## 关键假设

- 员工培训智能体属于 RAG 平台内嵌的固定流程 Agent，对外通过 App API Key 暴露能力。
- 应用端员工培训系统负责用户、计划审核、题库审核、页面展示和本地业务镜像，不作为课堂状态机的权威控制器。
- 已有 `app-runtime/structured-runs` 继续保留，用于兼容原有讲解和测验结构化运行；新增员工培训课堂接口承接更完整的流程控制。
- 旧的 `training/plans/drafts` 和 `training/questions/drafts` 硬编码 stub 必须替换为基于当前 App 知识库证据的草稿生成。

## 本轮范围

1. 平台侧补齐员工培训领域表、迁移、Schema、Service 和 API。
2. 平台侧提供学习计划草稿、题目草稿和课堂 Agent 会话/事件接口。
3. 课堂流程由平台状态机控制，返回 `uiActions`、`citations`、`control` 等结构化数据。
4. 应用端课堂服务改为调用平台课堂 Agent，并保存本地会话、事件和助手消息镜像。
5. 修正应用端调用平台对话接口时的字段名，使用 `conversationId`。

## 不做范围

- 不实现 SOP 作业助手、文件合规性检查和内部客服的业务接口。
- 不改造前端页面交互细节。
- 不引入新的模型 Provider、权限框架或通用 Agent 编排框架。
- 不提交 Git，不做 code review。

## 验收标准

- 平台学习计划接口不再返回固定 `doc-001`，而是基于当前 App 知识库 Chunk 生成可审核草稿。
- 平台题目接口至少支持选择题、判断题和主观题三类草稿。
- 平台课堂接口支持 `INIT -> PLAN -> TEACH -> QUIZ -> GRADE -> REVIEW -> SUMMARY -> COMPLETED` 的受控推进，并支持追问。
- 应用端课堂 API 不再解析自然语言标记生成按钮，而是直接使用平台返回的结构化 `uiActions`。
- 相关 Python 编译和培训链路测试通过。

## 验证命令

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_agent_runtime.py backend/app/tests/integration/test_employee_training_scenario_runtime.py backend/app/tests/unit/test_llm_quiz_generation.py -q
python -m pytest app/tests/unit/test_classroom_state_machine.py app/tests/unit/test_platform_client.py app/tests/integration/test_classroom_api.py -q
python -m compileall backend/app
python -m compileall app
git diff --check
```

## 与旧计划的差异

- `2026-05-27-training-stub-replacement.md` 中“应用端课堂本地状态机直接调用 `/app-runtime/chat-messages`”的路径调整为“应用端调用平台 `/training/classroom/*`，平台侧负责状态机和上下文管理”。
- 原应用端本地课堂状态机保留为测试用状态定义和本地镜像辅助，不再作为权威流程控制器。
- 平台侧重新创建培训领域表；此前 `0038_drop_training_tables.py` 删除的表通过新的迁移恢复。
