# 迭代计划 Sprint 28

## 1. Sprint 基本信息

- Sprint 名称：Sprint 28
- Sprint 主题：治理诊断可操作化
- 涉及 Epic：E22 知识库治理工作流强化
- 建议版本：内部增强
- 时间范围：待定
- 目标：让质量问题和索引同步诊断具备可定位、可理解、可重建的操作信息。

## 2. 关键假设

- Sprint 27 已完成 P05/P06/P07 的治理操作入口。
- 后端 DTO 只做兼容性扩展，不移除、不改名现有字段。
- 前端继续使用 `camelCase` 字段，保持与 OpenAPI 契约一致。

## 3. 本 Sprint 目标

- P06/P07 展示 index sync job 列表、目标副本、失败原因和重建结果。
- 质量问题增加可操作详情。
- 重复 Chunk 支持样例 Chunk 定位。
- `DocumentQualityIssueDTO` 增加可选字段：`contentHash`、`sampleChunkIds`、`recommendedAction`、`targetStore`。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S28-001 | B-122 | P06/P07 展示 index sync job 列表、目标副本、失败原因和重建结果 | P1 | 1.5d | Codex | Done |
| S28-002 | B-123 | 质量问题增加可操作详情，重复 Chunk 支持样例 Chunk 定位 | P1 | 1.5d | Codex | Done |

## 5. 验收标准

- OpenAPI 中的 `DocumentQualityIssueDTO` 包含新增可选诊断字段。
- 重复 Chunk 质量问题能返回内容哈希、样例 Chunk 和建议动作。
- P06/P07 能查询索引同步作业，并能触发索引副本重建。
- 失败原因和目标副本信息能在前端治理视图中呈现。

## 6. 范围边界

- 不引入新的诊断规则引擎。
- 不改变既有质量问题字段含义。
- 不把索引副本状态作为业务真值。
- 不做真实 Provider 网络级复测。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- 既有治理验证：`conda run -n rag-lab python scripts/verify_sprint16_kb_governance.py`
- Sprint 28 验证：`conda run -n rag-lab python scripts/verify_sprint28_governance_diagnostics.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`

## 8. 执行记录

- B-122：前端 service 增加索引同步作业查询和重建调用，P06/P07 增加索引同步作业展示与重建入口。
- B-123：质量问题 DTO 增加可操作诊断字段，后端质量摘要补充重复 Chunk 样例、建议动作和目标副本信息。
- 新增 `verify_sprint28_governance_diagnostics.py`，检查 DTO 字段、重复 Chunk 诊断实现和 P06/P07 索引同步入口。
