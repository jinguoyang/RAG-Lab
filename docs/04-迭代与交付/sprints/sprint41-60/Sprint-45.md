# 迭代计划 Sprint 45

## 1. Sprint 基本信息

- Sprint 名称：Sprint 45
- Sprint 主题：BindingRevision → ChunkRevision 重命名与 Rechunk 后端改造
- 涉及 Epic：E30 三层架构模型收口
- 建议版本：V1.9
- 时间范围：待排期
- 目标：完成数据库重命名、分块策略字段化、后端全量标识符替换和 rechunk API 实现。

## 2. 关键假设

- PostgreSQL 支持原生 `ALTER TABLE RENAME` + `ALTER TABLE RENAME COLUMN`，自动更新 FK 引用。
- 现有 `document_kb_bindings.chunk_size` / `chunk_overlap` 从未被 ingest worker 实际使用，可安全删除。
- 回填脚本写入默认策略 `fixed_size` + `{"chunk_size": 900, "chunk_overlap": 120}` 对现有数据无行为变更。
- `fixed_size` 是本 Sprint 唯一实现的分块策略，其他策略（semantic、token_split）仅预留 schema。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-225 | DB 迁移：RENAME binding_revisions → chunk_revisions 并新增 strategy/params 列 | P0 | 1d | Ready |
| B-226 | 后端标识符全量替换：binding_revision → chunk_revision（48 文件、731 处） | P0 | 2d | Ready |
| B-227 | 改造 ChunkRevision 创建逻辑，接入 strategy 和 params 参数 | P0 | 1d | Ready |
| B-228 | 改造初始绑定和 ingest worker，从 ChunkRevision 读取分块策略 | P0 | 1.5d | Ready |
| B-229 | 实现 rechunk API 端点和 rechunk job type | P0 | 2d | Ready |
| B-230 | 更新回填脚本适配新表名和列名 | P0 | 0.5d | Ready |
| B-231 | 补齐 rechunk 流程和 strategy/params 单元测试，全量后端测试回归 | P0 | 1.5d | Ready |

## 4. 验收标准

- `alembic upgrade head` 成功执行，表名、列名、FK、索引全部重命名。
- `chunk_revisions` 表新增 `strategy` 和 `params` 列，现有记录回填默认值。
- `document_kb_bindings` 表删除 `chunk_size` 和 `chunk_overlap` 列。
- 后端所有 Python 代码和测试中不再出现 `binding_revision` 标识符。
- `create_chunk_revision()` 接受 strategy/params 参数。
- `bind_documents_to_kb()` 从 KB metadata 读取分块策略写入 ChunkRevision。
- `run_ingest_job()` 从 ChunkRevision 读取策略传入 `parse_document()`。
- `POST /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/rechunk` 端点可用。
- rechunk 走 build-then-activate 流程：新 ChunkRevision building → active，旧的 retired。
- 全量后端测试通过。

## 5. 范围边界

- 不实现 semantic、token_split 等非 fixed_size 策略的实际分块逻辑。
- 不改造前端（Sprint 46）。
- 不更新文档和 OpenAPI（Sprint 46）。
- 不改变现有版本切换和首次绑定的行为语义，只改变数据存储位置。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab alembic upgrade head
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests
conda run -n rag-lab python scripts/export_openapi.py
```

```powershell
git diff --check
```

## 7. 实际结果

- DB 迁移 `0031_rename_binding_revisions_to_chunk_revisions` 已创建并验证。
- 后端标识符全量替换完成：`chunk_revision` 出现 305 处 / 17 文件，`binding_revision` 仅保留在历史迁移脚本中（预期）。
- ChunkRevision 创建逻辑已接入 strategy 和 params 参数。
- ingest worker 已从 ChunkRevision 读取分块策略。
- rechunk API 端点 `POST /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/rechunk` 已实现。
- 回填脚本 `migrate_binding_revisions.py` 和 `migrate_chunks.py` 已适配新表名和列名。
- 单元测试 `test_rechunk.py` 已补齐（5 个用例），全量后端测试 131/131 通过。
- 额外完成：KB 删除功能（级联删除、影响分析、API、前端弹窗、集成测试）和 Library Visibility 移除。

## 8. 关联文档

- [BindingRevision→ChunkRevision 重命名设计](../specs/2026-05-22-binding-to-chunk-revision-rename-design.md)
