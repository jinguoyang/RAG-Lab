# 迭代计划 Sprint 33

## 1. Sprint 基本信息

- Sprint 名称：Sprint 33
- Sprint 主题：App Runtime 生产化能力
- 涉及 Epic：E25 RAG 应用化封装
- 建议版本：V1.8
- 时间范围：待定
- 目标：在安全边界设计明确后，补齐 App Runtime SSE streaming、应用级限流、配额和调用统计，让 Runtime 更接近受控内部 API 发布标准。

## 2. 关键假设

- Sprint 32 已确定限流策略和错误码。
- blocking 接口语义保持稳定，SSE streaming 是新增响应模式，不破坏既有调用方。
- 限流和配额以应用级为最小粒度，暂不做商业化计费。

## 3. 本 Sprint 目标

- 支持 App Runtime SSE streaming 响应模式。
- 增加应用级限流和配额的最小实现。
- 增加调用统计摘要，支撑 P13 或观测模块展示调用量、失败率、延迟和无证据率。
- 补齐 streaming、限流和统计的回归验证。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S33-001 | B-139 | 支持 App Runtime SSE streaming 响应模式，不改变 blocking 接口语义 | P1 | 3d | Codex | Done |
| S33-002 | B-141 | 增加应用级限流、配额、调用统计和审计查询 | P1 | 3d | Codex | Done |

## 5. 验收标准

- `responseMode=blocking` 继续返回完整 JSON 响应，兼容 Sprint 30 契约。
- `responseMode=streaming` 可持续返回 answer delta、citation、usage 或 done 事件。
- 超出应用级限流或配额时返回稳定错误码，且不会执行 QARun。
- 调用统计可按应用维度查询并与 `app_invocations` 对账。

## 6. 范围边界

- 不做公网级网关、商业计费中心或复杂套餐。
- 不把 streaming 结果替代 QARun；最终仍要落 App Message、Invocation 和 QARun。
- 不新增自由工作流或插件执行能力。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- OpenAPI 导出：`conda run -n rag-lab python scripts/export_openapi.py`
- Runtime smoke：`conda run -n rag-lab python scripts/verify_app_runtime_smoke.py`
- Streaming / 限流回归：`conda run -n rag-lab python scripts/verify_app_runtime_smoke.py`
- 空白检查：`git diff --check`

## 8. 执行记录

- 已在 App Runtime 对话接口支持 `responseMode=streaming`，以 `text/event-stream` 返回 `answer_delta`、`citation`、`usage` 和 `done` 事件；blocking JSON 响应保持原契约。
- 已基于 `rag_apps.metadata.runtimeLimits` 或 `outputPolicy.runtimeLimits` 支持应用级 `minuteLimit` / `requestsPerMinute` 和 `dailyQuota` / `dailyRequestQuota`，超限时在创建 QARun 前返回 `RAG_APP_QUOTA_EXCEEDED`，并写入 failed invocation 审计。
- 已新增 `GET /api/v1/rag-apps/{appId}/stats`，按应用汇总调用量、失败率、平均延迟、限流次数和无证据率。
- 已扩展 `backend/scripts/verify_app_runtime_smoke.py`，覆盖 blocking 兼容、SSE streaming、限流审计和统计查询。
- 已将 B-139、B-141 的状态回写到 [产品待办清单](../../产品待办清单.md)。
