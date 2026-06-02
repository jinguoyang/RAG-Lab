# 迭代计划 Sprint 67

## 1. Sprint 基本信息

- Sprint 名称：Sprint 67
- Sprint 主题：结构化证据检索与 Corrective RAG
- 涉及 Epic：E34 高质量 RAG 核心优化
- 建议版本：V2.3
- 时间范围：待排期
- 目标：补齐表格、流程图等结构化证据检索，并在答案生成前加入受控证据不足重检索机制。

## 2. 关键假设

- Sprint 64 的 provenance 能提供表格和图形对象定位。
- Sprint 66 已提供多查询和上下文打包能力，可被 Corrective RAG 复用。
- Corrective RAG 是受控流程控制器，不是开放式自主 Agent。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 | Spec |
| --- | --- | --- | --- | --- | --- |
| B-324 | 表格与流程图结构化检索 | P0 | 3d | Done | [Spec](../../specs/2026-05-30-rag-table-flowchart-retrieval-spec.md) |
| B-325 | Agentic / Corrective RAG 重检索控制器 | P0 | 2d | Done | [Spec](../../specs/2026-05-30-rag-agentic-corrective-rag-spec.md) |

## 4. 验收标准

- 表格和流程图可作为结构化证据被检索。
- 结构化证据引用能定位到页码和 bbox。
- 证据不足时可触发受控重检索或拒答。
- Corrective RAG 有最大迭代次数、动作白名单和完整 trace。

## 5. 范围边界

- 不承诺所有复杂图自动完美理解。
- 不实现 Graph/RAPTOR 长文档多跳能力。
- 不允许控制器绕过权限过滤。

## 6. 验证命令

```powershell
python -m pytest backend/app/tests/unit/test_table_evidence_index.py backend/app/tests/unit/test_flowchart_evidence_index.py backend/app/tests/unit/test_corrective_rag_controller.py -q
python -m pytest backend/app/tests/integration/test_structured_evidence_retrieval.py backend/app/tests/integration/test_corrective_rag_runtime.py -q
python -m compileall backend/app
git diff --check
```

## 7. 关联文档

- [高质量 RAG 核心优化实施计划](../../plans/2026-05-30-high-quality-rag-core-optimization-plan.md)
- [结构化检索规范](../../specs/2026-05-30-rag-table-flowchart-retrieval-spec.md)
- [Corrective RAG 规范](../../specs/2026-05-30-rag-agentic-corrective-rag-spec.md)

## 8. 执行记录

- 2026-06-02: B-324 单元测试 13 项全部通过（含 search_flowcharts_by_step 和 flowchart_index_to_evidence 测试），B-325 单元测试 13 项全部通过。
- 2026-06-02: 代码已集成到 qa_run_service.py，structuredEvidence 和 correctiveRag trace 步骤正常写入。
- 2026-06-02: Sprint 67 收口完成，状态更新为 Done。
