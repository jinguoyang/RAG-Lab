# 高质量 RAG E2E 验收与评测集设计规范

> 用途：本文件是 B-327 / Sprint 68 的验收级 spec。当前状态以 `docs/04-迭代与交付/产品待办清单.md` 为准。

## 目标

建立高质量 RAG 的端到端评测集和验收脚本，用统一口径衡量解析、分块、检索、重排、上下文打包、答案生成和引用校验的质量收益。

## 范围

- 建立小型 golden set：FAQ、长文档、跨文档、多跳、表格、流程图、扫描 PDF、权限隔离。
- 评测指标包括 recall@k、MRR、citation accuracy、faithfulness、answer completeness、拒答正确率、延迟和成本。
- 每次评测记录 pipeline 配置、索引版本、模型版本和测试数据版本。
- 提供本地可运行的评测命令和报告输出。

## 不做

- 不把离线评测结果等同于线上用户满意度。
- 不引入无法复现的人工主观评分作为唯一标准。
- 不要求所有指标一次性达到最优。

## 设计要点

- golden set 数据应尽量小，但覆盖质量关键路径。
- 指标结果必须可对比，便于观察某个 Sprint 是否真的提升质量。
- 权限隔离样例必须包含“存在答案但当前用户无权访问”的情况。

## 开发注意项点

- 评测数据不能包含真实敏感业务文件。
- LLM judge 如被使用，必须记录模型、prompt 和原始评分理由。
- 评测脚本失败时应明确是环境问题、provider 问题还是质量回归。

## 验收标准

- 一条命令可运行核心 RAG E2E 评测。
- 报告能展示每类样例的指标和失败明细。
- 至少覆盖普通问答、表格问答、多跳问答和权限隔离。
- 配置变更前后可以生成可对比报告。

## 验证

```powershell
python -m pytest backend/app/tests/e2e/test_high_quality_rag_acceptance.py -q
python scripts/evaluate_high_quality_rag.py --fixture tests/fixtures/high_quality_rag
git diff --check
```
