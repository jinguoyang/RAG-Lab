# 员工培训端到端验收设计规范

> 用途：本文件是 B-315 / Sprint 62 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

建立覆盖平台和外部培训应用的员工培训端到端验收，确保“生成计划、审核发布、生成题库、课堂学习、答题评分、进度报表”形成真实闭环。

## 范围

- 平台 E2E 测试。
- 外部培训应用契约 E2E 测试。
- 前端构建验证。
- 文档和接口同步检查。

## 平台验收链路

1. 创建员工培训 App 和知识库材料。
2. 生成学习计划草稿。
3. 发布学习计划。
4. 生成并发布题目。
5. 创建课堂会话。
6. 完成 `PLAN -> TEACH -> CHECK_UNDERSTAND -> QUIZ -> GRADE -> REVIEW/SUMMARY`。
7. 写入进度和答题记录。
8. 查询报表。

## 应用端验收链路

1. 外部应用创建课堂会话。
2. 外部应用提交事件。
3. 外部应用渲染平台结构化动作。
4. 外部应用保存本地镜像。
5. 外部应用不调用 LLM 或 RAG Provider。

## 验收标准

- 平台和应用端 E2E 均通过。
- 所有关键输出包含 Citation 或可追溯证据。
- 跨 App 权限测试通过。
- `git diff --check` 通过。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_e2e.py -q
cd external-training-app/backend
python -m pytest app/tests/integration/test_training_e2e_contract.py -q
cd ../frontend
npm run build
```
