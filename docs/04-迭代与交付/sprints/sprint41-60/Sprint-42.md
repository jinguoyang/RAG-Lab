# 迭代计划 Sprint 42

## 1. Sprint 基本信息

- Sprint 名称：Sprint 42
- Sprint 主题：三层架构前端体验改造
- 涉及 Epic：E30 三层架构模型收口
- 建议版本：架构演进 V2.0
- 时间范围：待排期
- 目标：让用户在页面上能清楚理解文档库、知识库、智能应用三层边界，并能完成版本入库、版本切换、删除影响确认、权限来源查看和 Runtime 状态解释。

## 2. 关键假设

- Sprint 41 已提供稳定接口和错误码。
- 页面设计继续沿用现有 rag 组件和知识库模块风格。
- 普通用户主要理解文档、文档版本和知识库绑定版本，不直接操作 ParseRevision。
- 高风险操作必须使用统一确认弹窗或抽屉展示影响分析。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-209 | 改造文档库详情和版本管理交互，展示重复提醒、ParseRevision 状态、删除影响分析和强确认 | P0 | 2d | Ready |
| B-210 | 改造知识库文档中心，支持选择文档版本入库、绑定版本切换和 BindingRevision 状态展示 | P0 | 2d | Ready |
| B-211 | 改造 QA 历史和 Chunk 详情展示，支持证据回溯链路和 source_deleted 展示 | P0 | 1.5d | Ready |
| B-212 | 改造成员与权限页面，按三层展示角色、有效权限和用户组来源 | P1 | 1.5d | Ready |
| B-213 | 改造智能应用管理页面，展示所属知识库状态、Key 可用性、Runtime 拒绝原因和调用统计影响 | P1 | 1d | Ready |

## 4. 验收标准

- 文档库上传重复文件时有清晰提醒，但不强制阻止。
- 文档版本删除前展示 active 引用、运行中任务、历史 QA 引用等影响分析。
- 知识库绑定文档时可以选择具体文档版本。
- 知识库文档中心能展示 BindingRevision 的 building、active、retired、failed 状态。
- QA 历史中 source_deleted 证据展示“引用文件已被清理”。
- 权限页面能解释用户直接角色和用户组角色来源。
- P13 能展示知识库 disabled 对 App Runtime 的影响。

## 5. 范围边界

- 不重写页面整体布局。
- 不新增新的设计系统。
- 不实现复杂可视化图谱。
- 不暴露普通用户独立删除 ParseRevision 的入口。

## 6. 验证命令

```powershell
cd frontend
npm run lint
npm run test
npm run build
```

```powershell
git diff --check
```

## 7. 关联文档

- `../../plans/2026-05-21-e30-three-layer-architecture-refactor.md`
- `../../specs/2026-05-21-document-kb-app-architecture-briefing.md`
- `../../specs/2026-05-20-permission-role-model-design.md`
