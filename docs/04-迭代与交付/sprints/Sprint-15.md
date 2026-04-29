# 迭代计划 Sprint 15

## 1. Sprint 基本信息

- Sprint 名称：Sprint 15
- Sprint 主题：真实 Provider 生产化接入
- 涉及 Epic：E14 Provider 生产化接入
- 建议版本：V1.2
- 时间范围：待定
- 目标：补齐真实 Provider 的凭据配置、脱敏展示、连通性诊断、限流诊断、检索副本重建和发布环境复测报告。

## 2. 关键假设

- V1.1 已完成质量回归闭环，真实 Provider 接入开始影响发布可用性。
- 凭据仍通过环境变量或受控配置注入，仓库和文档不保存密钥。
- 基础 `/health` 继续保持轻量，真实 Provider 网络级探测通过显式诊断接口或脚本触发。
- Provider 失败必须返回可解释降级状态，而不是让 QA 主链路静默失败。

## 3. 本 Sprint 目标

- 支持真实 Provider 配置状态检查和脱敏展示。
- 支持 LLM、Embedding、Rerank Provider 的连通性与限流诊断。
- 支持 Dense、Sparse、Graph 检索副本重建和失败恢复脚本。
- 形成发布环境 Provider 复测报告模板。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S15-001 | B-065 | 实现真实 Provider 凭据配置、脱敏展示和本地校验 | P1 | 1d | Codex | Done |
| S15-002 | B-066 | 补齐 LLM、Embedding、Rerank Provider 连通性和限流诊断 | P1 | 1d | Codex | Todo |
| S15-003 | B-067 | 补齐 Dense、Sparse、Graph 检索副本重建和失败恢复脚本 | P1 | 1.5d | Codex | Todo |
| S15-004 | B-068 | 形成发布环境 Provider 复测报告模板和执行脚本 | P2 | 0.5d | Codex | Todo |

## 5. 验收标准

- Provider 配置检查可区分未配置、已配置但不可连、可连通、local/mock 降级。
- 诊断结果不暴露密钥、token、endpoint 敏感参数。
- 检索副本重建脚本能按知识库或文档版本触发，并记录失败原因。
- 发布复测报告能沉淀每类 Provider 的结果、环境限制和后续处理建议。

## 6. 范围边界

- 不要求所有真实 Provider 必须在本地在线。
- 不实现统一密钥管理平台，只约束配置读取、脱敏和诊断输出。
- 不新增复杂后台任务 UI，重建入口优先使用接口或脚本验证。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Sprint 15 验证脚本：`conda run -n rag-lab python scripts/verify_sprint15_provider_readiness.py`
- OpenAPI 导出：`conda run -n rag-lab python scripts/export_openapi.py`
- 空白检查：`git diff --check`
