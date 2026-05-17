# 迭代计划 Sprint 34

## 1. Sprint 基本信息

- Sprint 名称：Sprint 34
- Sprint 主题：App Runtime 治理回流与输入能力评估
- 涉及 Epic：E25 RAG 应用化封装
- 建议版本：V1.8
- 时间范围：待定
- 目标：让外部对话问题可以回流到 QARun 反馈和 EvaluationSample，并评估应用级输入变量、Prompt 模板和多租户预留是否进入后续版本。

## 2. 关键假设

- Sprint 30-33 已提供可调用、可管理、可审计和更生产化的 App Runtime。
- 治理回流必须继续以 QARun 和 EvaluationSample 为事实来源，不另建独立质量体系。
- 应用级输入变量和 Prompt 模板先评估真实使用点，不提前扩展成自由 DAG。

## 3. 本 Sprint 目标

- 支持外部对话反馈回流为 QARun 反馈或 EvaluationSample。
- 在管理端提供从调用记录进入反馈处理或样本沉淀的入口。
- 评估 `inputs`、应用级 Prompt 模板和多租户字段预留的必要性、范围和风险。
- 形成 V1.8 后续收口建议：进入实现、拆分新 Backlog 或推迟。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S34-001 | B-140 | 支持外部对话反馈回流为 QARun 反馈和 EvaluationSample | P1 | 3d | Codex | Done |
| S34-002 | B-144 | 评估应用级输入变量和 Prompt 模板能力，保持 PipelineDefinition 不变为自由 DAG | P2 | 1.5d | Codex | Done |
| S34-003 | B-149 | 多租户架构预留：评估 tenant_id 字段和 API Key 与租户绑定方案 | P1 | 1.5d | Codex | Done |

## 5. 验收标准

- 外部反馈能关联到原始 App Message、Invocation 和 QARun。
- 可选择将问题沉淀为 EvaluationSample，并保留来源摘要。
- 反馈回流不会暴露外部调用方不应看到的 Trace 或未授权正文。
- 输入变量、Prompt 模板和多租户预留有明确结论：实现、拆分或暂缓。

## 6. 范围边界

- 不实现复杂人工客服工单系统。
- 不把外部反馈作为自动调参依据，必须经过内部评估和配置治理链路。
- 不在没有明确使用点前扩展自由 Prompt 编排或多租户计费。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- OpenAPI 导出：`conda run -n rag-lab python scripts/export_openapi.py`
- Runtime smoke：`conda run -n rag-lab python scripts/verify_app_runtime_smoke.py`
- 反馈回流验证：`conda run -n rag-lab python scripts/verify_app_runtime_smoke.py`
- 前端构建（如改管理端入口）：`npm run build`
- 空白检查：`git diff --check`

## 8. 执行记录

- 已新增 `POST /api/v1/app-runtime/messages/{messageId}/feedback`，外部调用方只能对当前 App API Key 所属 App 的助手消息提交反馈。
- 反馈回流会更新关联 QARun 的 `feedback_status`、`feedback_note` 和 `metrics.failureType`，并可按请求创建 EvaluationSample；响应不返回 Trace、Evidence 正文或内部配置。
- 已确认 `inputs` 当前仅作为安全请求摘要和 QARun override 的 App Runtime 元数据保留，不改变 `PipelineDefinition` 拓扑；应用级 Prompt 模板暂缓，后续需至少两个真实外部应用使用点后再拆新 Backlog。
- 多租户结论：V1.8 不新增 `tenant_id` 迁移，也不改变 API Key 存储；后续如进入组织级隔离，应在 `rag_apps`、`rag_app_api_keys`、`app_conversations`、`app_messages`、`app_invocations` 与核心 KB 表统一增加租户字段，并同步唯一索引和鉴权上下文，不能只给 Key 追加孤立字段。
- 已扩展 `backend/scripts/verify_app_runtime_smoke.py` 覆盖反馈回流和 EvaluationSample 沉淀。
- 已将 B-140、B-144、B-149 的状态回写到 [产品待办清单](../../产品待办清单.md)。
