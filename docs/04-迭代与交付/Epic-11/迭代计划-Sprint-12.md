# 迭代计划 Sprint 12

## 1. Sprint 基本信息

- Sprint 名称：Sprint 12
- Sprint 主题：V1.0 验收硬化与参数生效闭环
- 时间范围：待定
- 目标：将现有 V1.0 功能闭环转成可重复验收、可复核权限边界、可确认配置参数生效的发布前验证闭环。

## 2. 关键假设

- Sprint 12 基于 B-001 至 B-052 已完成的功能面继续推进，不新增新的业务页面。
- 本轮只选择 `B-053`、`B-054`、`B-055`、`B-059`，暂不扩展到 Provider 网络级探测、批量评估报告或 P02/P05 统计增强。
- 验收脚本优先使用本地 Conda 环境 `rag-lab` 和现有前端构建命令，真实外部 Provider 可继续通过 local/mock 配置降级验证。
- P08 核心参数已经能保存到 `pipelineDefinition.nodes[].params`；本轮要验证并实现这些参数进入 QARun 执行链路。
- PostgreSQL 仍是业务真值中心，验收脚本必须覆盖跨 KB、inactive version 和权限裁剪等边界。

## 3. 本 Sprint 目标

- 建立 V1.0 端到端验收脚本，覆盖文档入库、配置保存激活、QA Run、历史回放和图支撑证据。
- 补齐权限与跨 KB 回归验证，重点防止 Provider 候选、图支撑 Chunk、inactive version 绕过 PostgreSQL 真值。
- 将验收清单 A-001 至 A-005 从空结果推进到可复核状态，保留脚本输出或手工确认备注。
- 让 P08 保存的核心参数参与 QA 执行，至少覆盖检索 topK、rerank topN、上下文 token、生成温度等关键参数。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S12-001 | B-053 | 建立 V1.0 端到端验收脚本 | P0 | 1d | Codex | Todo |
| S12-002 | B-054 | 补齐权限与跨 KB 回归用例 | P0 | 1d | Codex | Todo |
| S12-003 | B-055 | 将验收清单 A-001~A-005 半自动回填为可复核结果 | P0 | 0.5d | Codex | Todo |
| S12-004 | B-059 | 让 P08 保存的核心参数参与 QA 执行 | P0 | 1d | Codex | Todo |

## 5. 验收标准

- 可通过单一后端脚本或少量明确命令完成 V1.0 主链路验收，失败时输出可定位的接口、数据对象或断言原因。
- 验收覆盖文档上传/解析、active version 切换、配置保存/激活、QA Run 创建/详情、QA 历史回放、EvaluationSample 创建和图支撑 Chunk 查询。
- 权限回归用例能验证跨 KB 数据不可见、inactive version 不进入证据、Provider 返回候选必须经过 PostgreSQL 回表裁剪。
- P08 保存的 `pipelineDefinition.nodes[].params` 能在 QARun 执行中被解析并写入 trace/metrics，至少可观察到 topK、topN、maxContextTokens、temperature 的生效快照。
- `docs/05-测试与验收/验收清单.md` 中 A-001 至 A-005 有明确结果和备注，不再保留空结果。
- 后端应用代码可通过 Python 编译检查，前端可通过 Vite 构建，新增验收脚本可在本地环境运行。

## 6. 范围边界

- 不实现真实 Provider 的网络级深度探测；本轮只保留可选配置检查和本地验证。
- 不实现 EvaluationSample 的批量回归调度、评分规则和报告页面。
- 不重做 P09/P10 页面结构，只补参数生效所需的 trace/metrics 展示或适配。
- 不新增新的权限模型；本轮复用现有角色、ACL、ChunkAccessFilter 和 PostgreSQL 回表裁剪规则。
- 不把 P08 扩展成自由 DAG 或实验台；单次临时覆盖仍属于 P09。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Sprint 12 验收脚本：`conda run -n rag-lab python scripts/verify_sprint12_acceptance.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`
