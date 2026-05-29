# RAG 节点配置真实生效审计与可视化标识设计规范

> 用途：本文件是 B-316 / Sprint 63 的任务级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

建立 RAG Pipeline 节点配置项的真实生效审计机制，让平台能清楚区分 `effective`、`partiallyEffective`、`planned` 和 `deprecated` 配置，并在后端能力清单、运行 trace 与前端配置中心中一致展示。

## 当前问题

- 多个配置项已展示在 P08 配置中心，但后端没有读取或没有改变执行路径。
- 运行 trace 只能看到节点输入输出，无法证明某个配置项是否命中。
- 真实生效状态依赖人工理解代码，后续 agent 容易把“页面可配”误判为“运行有效”。

## 范围

- 梳理默认 Pipeline 中所有 RAG 节点及配置项。
- 新增配置能力清单 DTO，描述每个配置项的生效状态、执行位置和限制。
- QA Run trace 增加 `effectiveConfigs`、`ignoredConfigs` 或同等结构。
- P08 配置中心展示配置项生效状态和说明。

## 不做

- 不在本任务修复所有 no-op 配置，修复由 B-317 及后续任务承接。
- 不改动业务权限模型。
- 不替换现有 QA Run Pipeline。

## 设计要点

- 生效状态必须由后端维护，前端只渲染后端返回结果。
- `planned` 配置允许保留在页面，但必须明确说明当前不会影响运行结果。
- trace 中应记录实际使用的配置值，避免只记录用户提交的原始配置。
- 能力清单建议与 `default_pipeline.py` 的节点定义保持同源或强校验，避免漂移。

## 开发注意项点

- 配置项没有测试覆盖前不要标为 `effective`。
- 对安全相关配置项，例如权限过滤，说明必须强调它的最终执行位置。
- 对模型类配置项要说明 provider 是否支持运行时切换。

## 验收标准

- API 能返回所有默认节点的配置项生效状态。
- QA Run 执行结果能展示本次运行实际命中的配置项。
- 前端配置中心能区分已生效、部分生效和规划中配置。
- 至少覆盖 query rewrite、multi query、dense、sparse、graph、fusion、rerank、context packing、generation、citation、output 节点。

## 验证

```powershell
python -m pytest backend/app/tests/unit/test_rag_config_effectiveness.py -q
python -m pytest backend/app/tests/integration/test_qa_run_trace.py -q
cd frontend
npm run build
cd ..
git diff --check
```
