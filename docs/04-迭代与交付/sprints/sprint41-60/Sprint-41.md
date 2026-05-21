# 迭代计划 Sprint 41

## 1. Sprint 基本信息

- Sprint 名称：Sprint 41
- Sprint 主题：三层架构后端生命周期改造
- 涉及 Epic：E30 三层架构模型收口
- 建议版本：架构演进 V2.0
- 时间范围：待排期
- 目标：打通文档库 ParseRevision、知识库 BindingRevision、Chunk 生命周期、删除影响分析和 App Runtime 状态保护。

## 2. 关键假设

- Sprint 40 已完成核心数据模型和权限基线。
- 新旧数据结构允许在一个过渡期内兼容读取。
- 检索副本不是业务真值，清理失败应进入可重试任务。
- 删除操作必须先做影响分析，再允许用户强确认。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-202 | 文档库上传和版本管理接入文件 hash 重复提醒，并将解析正文沉淀为 ParseRevision | P1 | 1.5d | Ready |
| B-203 | 改造知识库文档绑定模型，支持 BindingRevision 生命周期 | P0 | 2d | Ready |
| B-204 | 改造 Chunk 生成和索引同步流程，仅 active Chunk 参与默认检索 | P0 | 2d | Ready |
| B-205 | 实现知识库绑定版本切换的先构建后激活流程 | P0 | 1.5d | Ready |
| B-206 | 实现文档、文档版本、ParseRevision 删除影响分析和强确认流程 | P0 | 2d | Ready |
| B-207 | QA Evidence 接入 source_deleted 状态 | P0 | 1d | Ready |
| B-208 | App Runtime 增加知识库启停保护和稳定错误码 | P1 | 0.5d | Ready |

## 4. 验收标准

- 文档解析产物可落到 ParseRevision，并能被知识库绑定选择。
- 同一 DocumentKbBinding 同一时刻只有一个 active BindingRevision。
- 新 BindingRevision 构建失败时旧 active BindingRevision 继续可检索。
- 默认检索只使用 active BindingRevision 下的 active Chunk。
- 删除支撑 active BindingRevision 的文档版本被拒绝。
- 删除仅被历史 QA 引用的旧版本允许强确认，并标记 Evidence 为 `source_deleted`。
- 知识库 disabled 时 App Runtime 返回稳定错误，不删除 App 和 Key。

## 5. 范围边界

- 不实现前端完整体验，只保证接口和服务层能力。
- 不实现自动清理策略。
- 不实现跨版本对比检索。
- 不在知识库保存完整解析文本副本。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests
conda run -n rag-lab python scripts/export_openapi.py
```

```powershell
git diff --check
```

## 7. 关联文档

- `../../plans/2026-05-21-e30-three-layer-architecture-refactor.md`
- `../../specs/2026-05-21-document-version-parse-revision-deletion-design.md`
- `../../specs/2026-05-21-knowledge-base-chunk-management-design.md`
