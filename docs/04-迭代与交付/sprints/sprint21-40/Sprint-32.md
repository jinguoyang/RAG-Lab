# 迭代计划 Sprint 32

## 1. Sprint 基本信息

- Sprint 名称：Sprint 32
- Sprint 主题：App Runtime 安全边界与真实 Provider 复测
- 涉及 Epic：E25 RAG 应用化封装
- 建议版本：V1.8
- 时间范围：待定
- 目标：在最小运行时和管理端可见性之后，收口 App Runtime 的安全边界设计，并在目标测试或预生产环境执行真实 Provider 网络级复测。

## 2. 关键假设

- Sprint 30 的 blocking Runtime 和 Sprint 31 的管理端可作为复测入口。
- 真实 Provider 复测必须使用目标环境凭据；不得用 `local`、`mock` 或 `identity` 成功结果替代真实结论。
- 安全边界先形成可执行设计，再决定是否进入限流、租户或更复杂凭据模型实现。

## 3. 本 Sprint 目标

- 明确 App API Key 格式、hash 存储、展示、撤销、轮换和过期策略。
- 明确应用级限流策略、隔离粒度、错误码和审计字段。
- 执行 Milvus、OpenSearch、Neo4j、LLM API、Embedding、Rerank 的真实网络级复测。
- 形成发布风险清单，区分代码问题、环境问题和后续生产化任务。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S32-001 | B-148 | App Runtime 安全边界设计：API Key、限流策略、跨知识库隔离粒度 | P0 | 2d | Codex | Done |
| S32-002 | B-147 | 真实 Provider 网络级连通性复测 | P0 | 2d | Codex | Done |

## 5. 验收标准

- 安全边界设计明确 API Key 生命周期、错误码、审计字段和跨 App / 跨 KB 隔离规则。
- 真实 Provider 复测记录覆盖成功、失败、超时、鉴权失败和响应格式异常。
- 复测结论回填到发布运维记录，不把本地 deterministic smoke 当作真实 Provider 通过。
- 发现的问题能明确归类为发布阻塞、后续任务或环境限制。

## 6. 范围边界

- 不在本 Sprint 实现完整限流配额，只完成设计和必要验证。
- 不引入多租户字段迁移；多租户只做预留影响评估。
- 不改动已通过的 blocking Runtime 语义，除非复测发现明确缺陷。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Runtime smoke：`conda run -n rag-lab python scripts/verify_app_runtime_smoke.py`
- 真实 Provider 复测：`conda run -n rag-lab python scripts/verify_provider_network_retest.py --output ..\docs\06-发布与运维\V1.8-Provider网络级复测记录.json --strict`
- 空白检查：`git diff --check`

## 8. 执行记录

- 已在 [接口设计说明](../../../03-系统设计/接口设计说明.md) 9.4 补齐 App Runtime 安全边界：API Key 生命周期、跨 App / 跨 KB 隔离、限流策略、错误码和审计字段。
- 已新增 `backend/scripts/verify_provider_network_retest.py`，对 Embedding、Milvus、OpenSearch、Neo4j、LLM 和 Rerank 执行真实网络级轻量探测，并将 `local_provider` / `blocked` 与真实成功明确区分。
- 已执行真实 Provider 复测，6 类 Provider 均返回 `success`；记录见 [V1.8 Provider 网络级复测记录](../../../06-发布与运维/V1.8-Provider网络级复测记录.md) 和同目录 JSON 证据。
- 已将 B-147、B-148 状态回写到 [产品待办清单](../../产品待办清单.md)。
- 已执行后端编译、App Runtime smoke、Provider 网络复测和空白检查。
