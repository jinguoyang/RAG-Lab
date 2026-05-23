# 迭代计划 Sprint 49

## 1. Sprint 基本信息

- Sprint 名称：Sprint 49
- Sprint 主题：员工培训助手运行时
- 涉及 Epic：E32 场景化智能应用
- 建议版本：V2.1
- 时间范围：待排期
- 目标：完成员工培训助手的讲解、测验生成、答题评分、错题解释和训练结果记录。

## 2. 关键假设

- Sprint 48 已完成场景向导、嵌入页基础框架和短期 Token。
- 培训助手不是完整 LMS，只记录 App Runtime 会话内的训练结果摘要。
- 培训测验和讲解仍必须回溯 QARun，不能绕过现有证据和权限链路。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-250 | 新增 structured-runs 接口支撑培训讲解和测验生成 | P0 | 2d | Done |
| B-251 | 新增培训答题提交和评分接口 | P0 | 2d | Done |
| B-252 | P13 试运行区支持培训讲解、测验和评分结果 | P0 | 2d | Done |
| B-253 | 嵌入页支持员工培训助手完整交互 | P0 | 2d | Done |
| B-254 | 训练结果写入 AppMessage metadata 并支持会话追溯 | P1 | 1.5d | Done |

## 4. 验收标准

- P13 可通过向导创建员工培训助手。
- 培训助手可根据主题生成讲解。
- 培训助手可生成指定数量、难度的测验题。
- 用户提交答案后返回分数、是否通过、逐题结果和错题解释。
- 训练结果写入 `app_messages.metadata.trainingResult`。
- P13 会话详情可追溯培训讲解、测验、答题结果和关联 QARun。

## 5. 范围边界

- 不做课程目录、班级、考试证书。
- 不做组织维度学习档案。
- 不做题库人工维护页面。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python -m pytest app/tests/integration/test_employee_training_scenario_runtime.py -q
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

## 7. 执行记录

- 已新增 `POST /api/v1/app-runtime/structured-runs`，支持 `training_explain` 和 `training_quiz_generate`。
- 已新增 `POST /api/v1/app-runtime/training/quiz-submissions`，支持答题评分、逐题结果和错题解释。
- P13 试运行区和嵌入页已支持培训讲解、测验生成、提交答案和评分展示。
- 训练结果写入 `app_messages.metadata.trainingResult`，结构化运行写入 `app_messages.metadata.trainingStructuredRun`，助手消息保留 `qa_run_id`。

## 8. 关联文档

- [场景化智能应用开发计划](../../plans/2026-05-24-agent-scenario-apps.md)
