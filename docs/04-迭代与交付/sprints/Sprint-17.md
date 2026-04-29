# 迭代计划 Sprint 17

## 1. Sprint 基本信息

- Sprint 名称：Sprint 17
- Sprint 主题：稳定性与观测
- 涉及 Epic：E16 稳定性与观测
- 建议版本：V1.3
- 时间范围：待定
- 目标：补齐 QARun、IngestJob、Provider 调用指标，建立慢链路诊断、错误摘要、任务补偿和备份恢复演练闭环。

## 2. 关键假设

- 观测优先服务研发排障和发布验收，不建设完整 APM 平台。
- 指标采集必须可控，不显著增加 QA 和 Ingest 主链路耗时。
- 备份恢复演练优先覆盖 PostgreSQL 业务真值和配置文档，不要求一次覆盖所有外部副本。
- 任务补偿必须以幂等为前提，避免重复写入检索副本。

## 3. 本 Sprint 目标

- 采集 QARun、IngestJob 和 Provider 调用关键指标。
- 增加慢链路诊断、错误摘要和健康面板接口。
- 补齐任务幂等、补偿和重复执行回归用例。
- 建立备份恢复演练脚本和恢复结果回填文档。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S17-001 | B-073 | 采集 QARun、IngestJob 和 Provider 调用关键运行指标 | P1 | 1d | Codex | Todo |
| S17-002 | B-074 | 增加慢链路诊断、错误摘要和健康面板接口 | P1 | 1d | Codex | Todo |
| S17-003 | B-075 | 补齐任务幂等、补偿和重复执行回归用例 | P1 | 1.5d | Codex | Todo |
| S17-004 | B-076 | 建立备份恢复演练脚本和恢复结果回填文档 | P2 | 1d | Codex | Todo |

## 5. 验收标准

- QARun、IngestJob 和 Provider 调用具备耗时、状态、错误摘要和关联资源 ID。
- 慢链路诊断可以定位慢在检索、rerank、生成、权限裁剪或文档处理阶段。
- 重复执行同一个补偿任务不会产生重复主数据或不可解释副本状态。
- 备份恢复演练能记录执行时间、恢复对象、结果和遗留风险。

## 6. 范围边界

- 不接入完整 APM、Prometheus 或告警平台，除非后续明确要求。
- 不把 `/health` 变成重型依赖探测。
- 不承诺外部检索副本不可丢失，副本以可重建为原则。

## 7. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- Sprint 17 验证脚本：`conda run -n rag-lab python scripts/verify_sprint17_observability.py`
- OpenAPI 导出：`conda run -n rag-lab python scripts/export_openapi.py`
- 空白检查：`git diff --check`
