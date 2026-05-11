# 迭代计划 Sprint 11

## 1. Sprint 基本信息

- Sprint 名称：Sprint 11
- Sprint 主题：发布验收与运维治理
- 涉及 Epic：E10 发布验收与运维治理
- 时间范围：已完成
- 目标：补齐 V1.0 发布前所需的审计日志、OpenAPI Schema、依赖健康检查、部署说明和发布验证脚本。

## 2. 关键假设

- Sprint 11 只补发布治理的最小闭环，不引入复杂 CI/CD 平台。
- `/api/v1/health` 保持轻量，依赖配置和降级状态通过依赖健康检查或发布脚本验证。
- OpenAPI Schema 是接口治理的可复核产物，需要能被本地脚本稳定导出。

## 3. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- |
| S11-001 | B-047 | 实现关键操作审计日志写入与查询排障字段 | P0 | Codex | Done |
| S11-002 | B-048 | 生成或维护 OpenAPI Schema，并补充接口级最小验证脚本 | P1 | Codex | Done |
| S11-003 | B-049 | 补充本地/测试环境部署配置、外部依赖健康检查和备份恢复说明 | P1 | Codex | Done |
| S11-004 | B-050 | 梳理 V1.0 验收脚本，并回填验收清单结果 | P0 | Codex | Done |

## 4. 验收标准

- 关键操作可写入审计日志，并支持按资源、操作者和时间范围查询。
- OpenAPI Schema 可导出到 `docs/06-发布与运维/openapi.json`。
- 发布与运维手册包含本地/测试环境部署、依赖健康检查、备份恢复和回滚说明。
- 发布验证脚本能覆盖 OpenAPI、审计日志和依赖健康检查的最小契约。

## 5. 验证命令

- 后端编译：`conda run -n rag-lab python -m compileall app`
- OpenAPI 导出：`conda run -n rag-lab python scripts/export_openapi.py`
- Epic10 发布治理验证：`conda run -n rag-lab python scripts/verify_epic10_release_ops.py`
