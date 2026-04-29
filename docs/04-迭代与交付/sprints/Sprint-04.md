# 迭代计划 Sprint 04

## 1. Sprint 基本信息

- Sprint 名称：Sprint 04
- Sprint 主题：E3 配置中心最小链路
- 时间范围：待定
- 目标：完成 Config Template / Config Revision 的最小数据模型、Pipeline 校验、Revision 保存与激活接口，并让前端配置中心接入真实数据。

## 2. 关键假设

- Sprint 04 基于 Sprint 03 已完成的开发期认证、知识库、文档中心和 PostgreSQL 迁移基础继续推进。
- 本 Sprint 只实现受约束 Pipeline 的配置保存与激活，不实现 QA Run 执行链路。
- `pipelineDefinition` 是后端执行契约，不保存画布坐标、颜色、图标等纯展示字段。
- 权限沿用当前开发期最小规则：平台管理员可管理全部可见知识库配置；完整角色矩阵留到后续迭代。

## 3. 本 Sprint 目标

- 新增 `config_templates`、`config_revisions` 相关迁移，字段与设计文档保持一致。
- 实现 Pipeline 校验接口，覆盖最小安全规则。
- 实现 Revision 保存、列表、详情和激活接口，保存与激活严格分离。
- 前端 P08 配置中心接入真实接口，保留受约束 Pipeline Designer 的交互护栏。
- 保持范围克制：不实现 QARun、Provider 执行、Revision Diff 和从 QARun 沉淀草稿。

## 4. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S4-001 | B-014 | 实现 Config Template / Config Revision 表与迁移 | P0 | 1d | Codex | Done |
| S4-002 | B-015 | 实现 Pipeline 校验、保存 Revision、激活 Revision 接口 | P0 | 2d | Codex | Done |
| S4-003 | B-016 | 接入配置中心 Revision 列表、保存、激活和校验反馈 | P0 | 2d | Codex | Done |

## 5. 建议实现顺序

1. 数据库迁移：新增配置模板和配置版本表，先不引入 QA Run 表。
2. 后端 Schema 与服务：新增 Pipeline、Template、Revision DTO，保持 API 字段使用 `camelCase`。
3. Pipeline 校验：基于受约束 DSL 执行最小规则校验，并返回规范化后的定义。
4. Revision 接口：保存前强制校验，激活时同事务更新旧 active、新 active、知识库指针和审计摘要。
5. 前端接入：沿用 `types / services / adapters / pages` 分层，P08 不直接散落 API 路径和 DTO 转换。
6. 验证与文档：补充迁移、接口、前端构建和联调验证说明。

## 6. 验收标准

- 后端可以执行 Alembic 迁移到 `0004_config_tables` 或后续 head。
- 数据库中存在配置模板、配置版本相关基础表和必要索引。
- `POST /api/v1/knowledge-bases/{kbId}/config-revisions/validate` 能返回校验结果和错误码。
- `POST /api/v1/knowledge-bases/{kbId}/config-revisions` 能保存新的 saved Revision，但不自动生效。
- `POST /api/v1/knowledge-bases/{kbId}/config-revisions/{revisionId}/activate` 能切换 active Revision。
- 前端 P08 能展示真实 Revision 列表，保存后出现新版本，激活后更新生效版本。
- 前端构建、后端编译和核心接口 TestClient 验证通过。

## 7. 范围边界

- 不实现 QA Run 创建、状态轮询、详情和历史。
- 不接入 LLM、Embedding、Rerank、Milvus、OpenSearch 或 Neo4j。
- 不实现 Revision Diff、模板创建后台、从 QARun 生成草稿。
- 不重构 P08 的整体视觉结构，只做真实数据接入所需的最小改动。

## 8. 已确认信息

- E3 对应产品待办 `B-014` 至 `B-016`。
- 配置中心页面对应原型 P08。
- Pipeline 校验、保存和激活接口来源为 `接口设计说明.md` 6.6 至 6.8。
- PostgreSQL 仍是 Config Revision 和 active 指针的业务真值中心。

## 9. 决策记录

### S4-001 配置中心最小数据范围

- 决策：Sprint 04 先落 `config_templates` 和 `config_revisions`，暂不落 QA Run 相关表。
- 原因：本轮目标是配置中心保存与生效闭环；QA 执行和 Trace 持久化属于 E4。
- 后续：实现 QA Run 时，使用 active `config_revision_id` 锁定运行时配置。

### S4-002 后端 Pipeline 校验范围

- 决策：本轮校验覆盖受约束模式、节点结构、至少一路检索、锁定节点不可禁用、权限过滤在生成前、Query Rewrite 在检索前、Graph 回落 Chunk 和 Citation 必须启用。
- 原因：这些规则是保存和激活配置前的最小安全边界，足以支撑 P08 真实联调。
- 后续：Provider 能力声明、Diff、模板后台和从 QARun 沉淀草稿留到后续迭代。

### S4-003 P08 真实接口接入

- 决策：P08 保留现有受约束画布交互，只将后端校验、保存 Revision、版本列表和激活动作接入真实接口。
- 原因：本轮目标是配置中心最小闭环，不扩大到重做视觉结构或 QA 执行链路。
- 后续：P09 实现后，可复用 active Revision 和 `pipelineDefinition` 生成 Executed Pipeline Trace。

## 10. Epic Review 记录

- Review 发现：Pipeline 校验接口应先确认知识库对当前用户可见，避免绕过知识库维度的访问边界。
- Review 发现：`sourceTemplateId` 应在 Schema 层声明为 UUID，避免非法字符串进入服务层后产生非预期异常。
- 处理结果：已补充可见性检查，并将非法 `sourceTemplateId` 收敛为接口参数校验错误。
