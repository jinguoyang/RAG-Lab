# 迭代计划 Sprint 35

## 1. Sprint 基本信息

- Sprint 名称：Sprint 35
- Sprint 主题：前端动作驱动的真实数据验收硬化
- 涉及 Epic：E26 前端动作驱动的真实数据验收硬化、E10 发布验收与运维治理
- 建议版本：内部增强
- 时间范围：待定
- 目标：从前端真实操作出发，验证 RAG App 管理、App Runtime 调用、反馈回流、调用审计、QA 历史回溯和真实 Provider 链路均使用真实服务与真实数据。

## 2. 关键假设

- V1.8 的 RAG App 后端管理接口、App Runtime blocking / streaming、反馈回流和调用审计已具备最小链路。
- 本 Sprint 优先补齐验证能力和前端真实动作闭环，不扩展自由 DAG、插件市场、多租户计费或复杂 Prompt 编排。
- local/mock Provider smoke 只能证明本地接口路径，不作为真实 Provider 验收结论。
- 若真实 Provider、数据库、对象存储或 Langfuse 服务不可用，应在执行记录中标为环境阻塞，不用演示数据替代。

## 3. 本 Sprint 目标

- 补齐前端 ESLint、Vitest 和统一验证脚本入口。
- 让 P13 可以通过用户输入的 App API Key 发起真实 App Runtime 调用，并展示 answer、Citation、runId、messageId 和 usage。
- 让 P13 可提交外部反馈，回流到 QARun 和 EvaluationSample。
- 让调用记录可跳转到 QA 历史并打开关联 QARun，形成内部治理闭环。
- 建立浏览器驱动的前端真实动作验收脚本，并补充真实 Provider + 真实文档端到端复测口径。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S35-001 | B-146 | 前端补齐 ESLint + Vitest 基础工程化配置，支持 lint 和单元测试 | P0 | 1d | Codex | Done |
| S35-002 | B-150 | 增加 App Runtime 前端服务层，覆盖 blocking、streaming 和反馈回流调用 | P0 | 1d | Codex | Done |
| S35-003 | B-151 | P13 增加真实 Runtime 试运行面板、调用统计、Key 过期时间和服务端状态筛选 | P0 | 2d | Codex | Done |
| S35-004 | B-152 | 从 P13 调用记录按 runId 跳转到 P10 并自动打开关联 QARun 详情 | P1 | 1d | Codex | Done |
| S35-005 | B-153 | 建立浏览器驱动的 P13 真实动作 E2E 验收脚本 | P0 | 1.5d | Codex | Done |
| S35-006 | B-154 | 建立真实文档和真实 Provider 端到端验收记录 | P0 | 1.5d | Codex | Done |
| S35-007 | B-155 | 补齐 App Conversation / Message 只读详情接口和 P13 详情视图 | P1 | 1d | Codex | Done |

## 5. 验收标准

- 前端具备可重复执行的 lint、unit test 和 build 命令。
- P13 的试运行不读取演示数组或硬编码答案，必须调用 `/api/v1/app-runtime/chat-messages`。
- P13 试运行结果返回的 `runId` 可以在 P10 打开并看到 QARun 详情、Evidence、Citation 和 Trace。
- 外部反馈可以从 P13 进入 Runtime 反馈接口，并在 QARun 反馈或 EvaluationSample 中留下记录。
- 浏览器 E2E 脚本通过页面动作完成创建应用、生成 Key、Runtime 调用、反馈、撤销 Key 和错误态验证。
- 真实 Provider 端到端验收必须引用真实上传文档产生的 PostgreSQL Chunk；local/mock Provider 结果不得标记为真实验收通过。

## 6. 范围边界

- 不新增自由 DAG、低代码工作流、插件市场或复杂 Agent 编排。
- 不新增商业化租户、计费中心或复杂配额售卖能力。
- 不把 App Conversation 和 App Message 替代 QARun；QARun 仍是执行事实来源。
- 不把 local/mock smoke、静态脚本或页面硬编码数据当作真实 Provider 端到端验收。

## 7. 验证命令

- 前端 lint：`npm run lint`
- 前端单元测试：`npm run test`
- 前端构建：`npm run build`
- P13 管理页脚本：`node .\scripts\verify_rag_app_management_ui.mjs`
- P13 真实动作契约：`node .\scripts\verify_p13_runtime_action_flow.mjs`
- 后端编译：`conda run -n rag-lab python -m compileall app`
- OpenAPI 导出：`conda run -n rag-lab python scripts/export_openapi.py`
- App Runtime smoke：`conda run -n rag-lab python scripts/verify_app_runtime_smoke.py`
- App Conversation 详情：`conda run -n rag-lab python scripts/verify_app_conversation_detail.py`
- App Runtime 真实 Provider E2E：`conda run -n rag-lab python scripts/verify_app_runtime_real_provider_e2e.py`
- 文档空白检查：`git diff --check`

## 8. 执行记录

- 2026-05-16：已确认当前前端仅有 `dev` / `build`，尚无正式 lint / test；Sprint 35 第一项从 B-146 开始。
- 2026-05-16：曾尝试以 Vitest 用例覆盖 Pipeline diff 并运行 `npm run test -- --run`，结果因缺少 `test` script 失败；用户确认暂时跳过 B-146 后，未保留未接入测试文件。
- 2026-05-16：安装 ESLint / Vitest 依赖时 npm registry 返回 `ECONNRESET`，固定 ESLint 9 版本后仍超时且未写入 `package.json` / `package-lock.json`；B-146 暂按环境阻塞处理，继续推进 B-150。
- 2026-05-16：已新增 `frontend/src/app/types/appRuntime.ts`、`frontend/src/app/services/appRuntimeService.ts` 和 `frontend/scripts/verify_app_runtime_service.mjs`；服务层覆盖 blocking、streaming、反馈回流、SSE 解析和 Bearer API Key header，不持久化 API Key 明文。
- 2026-05-16：已扩展 P13 管理页，支持应用级调用统计、服务端状态筛选、API Key 过期时间输入、真实 Runtime blocking / streaming 试运行，以及基于试运行结果提交负反馈并创建评估样本。
- 2026-05-16：已实现 P13 调用记录和会话摘要的 QARun 深链，链接携带 `runId` 查询参数；P10 会读取 URL 中的 `runId`，在历史列表加载后自动打开匹配 QARun 详情。
- 2026-05-16：已新增 `frontend/scripts/verify_p13_runtime_action_flow.mjs`，并通过内置浏览器实际执行 P13 创建应用、生成完整 App API Key、blocking Runtime 调用、反馈回流、撤销 Key、撤销后调用失败验证；页面无框架错误覆盖，残留 1 条既有 ConfirmDialog ref warning。
- 2026-05-16：已新增 `backend/scripts/verify_app_conversation_detail.py`，并补齐 `GET /api/v1/rag-apps/{appId}/conversations/{conversationId}` 只读详情接口；P13 会话页可读取真实 `app_conversations` 和 `app_messages` 时间线，并保留关联 QARun 跳转。
- 2026-05-16：已运行真实 Provider 网络级复测严格模式，Embedding、Milvus、OpenSearch、Neo4j、LLM、Rerank 均返回 success；JSON 证据已更新至 `docs/06-发布与运维/V1.8-Provider网络级复测记录.json`。
- 2026-05-16：已新增并运行 `backend/scripts/verify_app_runtime_real_provider_e2e.py`，真实上传文本、执行入库、调用 App Runtime，返回 `citationCount=1`，并回查 PostgreSQL Chunk `48b15ad3-c4b6-4f30-a89b-91a6e8e86b2f` 包含本次 marker `b154-bec56cc9`；Langfuse 记录期间出现 Bad gateway 日志，但未阻断 Provider、入库、Runtime 或 Citation 验证。
- 2026-05-17：已完成 B-146，前端新增 ESLint 9 扁平配置、Vitest 配置和 Pipeline diff 单元测试；已执行 `npm run lint`、`npm run test`、`npm run build`，其中 build 保留既有 chunk size warning。
