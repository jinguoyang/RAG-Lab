# 迭代计划 Sprint 27

## 1. Sprint 基本信息

- Sprint 名称：Sprint 27
- Sprint 主题：知识库治理工作流接入
- 涉及 Epic：E22 知识库治理工作流强化
- 建议版本：内部增强
- 时间范围：待定
- 目标：把已有治理后端能力接入 P05/P06/P07，让治理摘要、批量文档治理和 Chunk 治理标记形成可操作入口。

## 2. 关键假设

- V1.7 已完成，当前不建立新的 Release。
- 后端已有质量摘要、批量治理、Chunk 排除和索引重建接口。
- 本 Sprint 优先补齐前端工作流，不做真实 Provider 网络级复测。

## 3. 本 Sprint 目标

- P05 治理待办支持按问题跳转到文档或 Chunk。
- P06 支持多选文档、批量重解析、批量停用和批量重建索引，并复用二次确认。
- P07 Chunk 详情支持排除标记、治理备注保存和状态刷新。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S27-001 | B-119 | P05 治理待办支持按问题跳转到文档或 Chunk | P1 | 1d | Codex | Done |
| S27-002 | B-120 | P06 支持多选文档、批量重解析、批量停用和批量重建索引 | P1 | 1.5d | Codex | Done |
| S27-003 | B-121 | P07 Chunk 详情支持排除标记、治理备注保存和状态刷新 | P1 | 1.5d | Codex | Done |

## 5. 验收标准

- P05 的质量问题可以带着文档或 Chunk 定位信息跳转。
- P06 批量治理操作能复用现有后端批量治理接口，并保留二次确认。
- P07 能保存 Chunk 排除标记和治理备注，保存后刷新治理状态。
- 不改变 PostgreSQL 作为业务真值的边界；Chunk 排除只影响后续检索和 QA。

## 6. 范围边界

- 不新增复杂规则引擎。
- 不做全文人工编辑器。
- 不新增前端测试框架。
- 不处理上线部署和真实 Provider 复测。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- 既有治理验证：`conda run -n rag-lab python scripts/verify_sprint16_kb_governance.py`
- Sprint 27 验证：`conda run -n rag-lab python scripts/verify_sprint27_governance_workflow.py`
- 前端构建：`npm run build`
- 空白检查：`git diff --check`

## 8. 执行记录

- B-119：P05 治理摘要增加问题跳转逻辑，支持携带治理问题上下文进入文档详情。
- B-120：P06 增加文档多选、批量治理操作、目标副本选择和索引重建触发入口。
- B-121：P07 Chunk 抽屉增加治理标记区域，支持排除 Chunk、治理备注保存和状态刷新。
- 新增 `verify_sprint27_governance_workflow.py`，检查 OpenAPI 治理接口、前端 service 和 P05/P06/P07 接入点。
