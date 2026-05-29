# 员工培训权限隔离与安全边界设计规范

> 用途：本文件是 B-313 / Sprint 62 的设计规范，属于后续实现的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

强化员工培训 Agent 的跨 App、跨员工、跨计划访问隔离，并明确外部应用不能接触平台内部模型能力和未授权证据。

## 范围

- 会话事件校验 API Key 归属 App。
- 会话读取校验 App 和外部用户。
- 计划、题库、进度和报表按 App 隔离。
- 响应不暴露完整 Prompt、内部 Trace、Provider 密钥或未授权 Chunk 正文。

## 安全规则

- `credential.appId == resource.appId`。
- 普通员工只能访问自己的 `endUserId` 会话。
- 管理员接口必须通过平台管理权限或应用端服务端代理。
- 浏览器端不得保存长期平台 API Key。

## 验收标准

- App B 的 API Key 不能推进 App A 的课堂。
- 员工 B 不能读取员工 A 的课堂状态。
- 报表不能跨 App 聚合。
- 错误响应使用稳定错误码，不泄漏资源存在性。

## 验证

```powershell
python -m pytest backend/app/tests/integration/test_employee_training_security.py backend/app/tests/integration/test_employee_training_agent_runtime.py -q
python -m compileall backend/app
```
