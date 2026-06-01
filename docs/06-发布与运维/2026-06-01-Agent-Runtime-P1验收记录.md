# Agent Runtime P1 验收记录

> 用途：本文记录 E35 / B-328 平台 Agent Runtime 基座的真实环境验收证据。本文是执行证据，不替代 Backlog、Sprint 或 Release 状态源。

## 1. 当前结论

截至 2026-06-01，P1 机器门禁已在独立 PostgreSQL 测试库和真实 LLM Provider 环境通过。B-328 仍保持 `In Review`，原因是平台级规范中的部分 Code Review 条件尚未落实到代码。

## 2. 验收环境

- PostgreSQL：使用独立测试库 `rag_lab_agent_runtime_test`，不使用业务库。
- Provider：使用当前后端 `.env` 中配置的 OpenAI-compatible LLM Provider。
- Python：使用 Conda 环境 `rag-lab`。
- 验收脚本：`backend/scripts/verify_agent_runtime_foundation.py`。

## 3. 严格机器门禁

执行：

```powershell
$env:RAG_LAB_TEST_POSTGRES_URL="postgresql://<user>:<password>@<host>:5432/rag_lab_agent_runtime_test"
conda run -n rag-lab python backend/scripts/verify_agent_runtime_foundation.py
```

结果：退出码 `0`。

| 检查项 | 结果 | 摘要 |
| --- | --- | --- |
| `compileCheck` | PASS | `backend/app` 与 `backend/scripts` 编译通过 |
| `unitTests` | PASS | 32 passed |
| `regressionTests` | PASS | 26 passed |
| `scriptEntrypoints` | PASS | 两个脚本 `--help` 均退出码为 0 |
| `postgresCheckpoint` | PASS | 1 passed，覆盖官方 Checkpointer 初始化、写入和恢复 |
| `providerProbe` | PASS | `chat`、`toolCalling`、`structuredOutput`、`summarization` 均为 `true` |
| `configSync` | PASS | `.env.example` 配置项同步完成 |

Provider 探测 stdout 已保持为纯 JSON。当前环境仍会在 stderr 输出可选依赖告警：

```text
Error importing huggingface_hub.hf_api: No module named 'filelock'
```

该告警未影响本轮四项 Provider 能力探测结果，后续依赖治理时单独处理。

## 4. 性能基线

本轮为 P1 基座级采样，用于后续对照，不作为生产容量结论。

| 指标 | 样本数 | P50 | P95 |
| --- | ---: | ---: | ---: |
| `checkpoint.setup` | 1 | 453.215 ms | - |
| Checkpoint Graph invoke + get state | 30 | 410.995 ms | 769.986 ms |
| Shadow projection | 1000 | 0.000900 ms | 0.001000 ms |
| QARun Tool 额外包装耗时 | 100 | 0.453 ms | 0.854 ms |

## 5. 尚未收口的 Code Review 条件

以下事项仍阻断 B-328 从 `In Review` 更新为 `Done`：

- `skill_adapter.py` 尚未实现平台规范要求的 Schema、超时和审计边界。
- 尚未实现 Graph、Tool 与 `QARun` 的 Trace 串联。
- `qa_run_tool.py` 会通过 App Runtime 写入 Conversation、Message、Invocation 和 `QARun` 记录，需要明确“只读 Tool”的副作用边界和重放幂等约束。
- Shadow 当前只执行无副作用状态投影，尚未形成状态镜像差异记录。

上述事项应作为 B-328 的后续 Code Review 修复范围处理，不混入 B-329 课堂 Graph 编排。
