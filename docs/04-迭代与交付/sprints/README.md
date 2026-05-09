# Sprint 总览

Sprint 是时间盒，用于承接一轮可验证交付。本文维护当前 Sprint 状态和历史 Sprint 索引，不再重复保存每个 Sprint 的完整计划表。

## 1. 当前状态

- 当前没有进行中的 Sprint。
- Sprint 01 至 Sprint 26 已完成，对应 V1.0 至 V1.7。
- V1.7 已通过 Sprint 25 和 Sprint 26 完成 E21 RAG 模块化调优范围：P08 支持受控 RAG Pipeline 节点参数配置，QARun 固化 Pipeline Snapshot 和节点级参数快照，P10 支持配置效果对比和优化建议展示，并已补充 V1.7 RAG 调优指南。
- 新增工作应先进入 [产品待办清单](../产品待办清单.md)，再建立新的 Sprint 文档。

## 2. 历史 Sprint 索引

| Sprint 范围 | 版本 | 主题 | 状态 | 明细 |
| --- | --- | --- | --- | --- |
| Sprint 01-12 | V1.0 | 工程启动、基础业务、文档中心、配置中心、QA、权限、验收硬化 | Done | `Sprint-01.md` 至 `Sprint-12.md` |
| Sprint 13-14 | V1.0 / V1.1 | Provider 诊断、质量回归、配置优化闭环 | Done | `Sprint-13.md`、`Sprint-14.md` |
| Sprint 15-18 | V1.2 / V1.3 | Provider 生产化、知识库治理、稳定性观测、协作治理 | Done | `Sprint-15.md` 至 `Sprint-18.md` |
| Sprint 19-22 | V1.4 / V1.5 | 真实入库、多副本写入、真实检索、回放复跑 | Done | `Sprint-19.md` 至 `Sprint-22.md` |
| Sprint 23-26 | V1.6 / V1.7 | 真实 RAG 端到端闭环、模块化调优、评估对比 | Done | `Sprint-23.md` 至 `Sprint-26.md` |

## 3. 单个 Sprint 文档约定

单个 Sprint 文档是历史执行记录，至少保留：

- Sprint 基本信息和涉及 Epic。
- 关键假设和范围边界。
- 计划事项，逐项关联 Backlog。
- 验收标准和验证命令。
- Sprint 结束后的实际结果、遗留问题和下一步建议。

## 4. 维护规则

- 当前 Sprint 状态只在本文件维护。
- 单个 Sprint 文档完成后作为归档记录，不再为了同步总览状态而反复改写。
- 若历史 Sprint 文档与当前实现存在差异，以产品待办清单、Release 总览和最新验证脚本结果为准。
