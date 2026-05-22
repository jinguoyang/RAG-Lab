# BindingRevision → ChunkRevision 重命名与 Rechunk 能力设计

## 1. 设计目标

当前 `BindingRevision` 命名暗示它描述的是"绑定关系的版本"，但实际上它承载的是**一次分块构建的完整结果**——包括分块策略、构建状态、chunk 数量和生命周期。当需要支持"同一 ParseRevision 用不同策略重新分块"时，"BindingRevision"的语义更加不匹配。

本设计需要达成以下目标：

- 将 `BindingRevision` 重命名为 `ChunkRevision`，使命名与实际职责一致。
- 引入 `strategy`（独立列）和 `params`（JSONB 列）替代固定的 `chunk_size`/`chunk_overlap`，支持多种分块策略。
- 实现 rechunk 能力：对已绑定的 ParseRevision 使用不同分块策略重新生成 ChunkRevision。
- 保持六层回溯链完整：`Document → DocumentVersion → ParseRevision → ChunkRevision → Chunk → QARunEvidence`。
- 分两期交付：Sprint 45 完成后端全量改造，Sprint 46 完成前端和文档同步。

## 2. 核心原则

1. **策略只在 ChunkRevision 层**：分块策略（strategy + params）只记录在 ChunkRevision 上，`document_kb_bindings` 不保留分块配置。
2. **初始绑定从 KB metadata 读默认策略**：首次绑定时从知识库 metadata 读取默认分块参数，创建第一个 ChunkRevision。
3. **Rechunk 走 build-then-activate**：与版本切换相同，新 ChunkRevision 先 building，完成后激活，旧的退役。
4. **PG 原生 RENAME**：使用 `ALTER TABLE RENAME` + `ALTER TABLE RENAME COLUMN`，不新建表。
5. **向下兼容回填**：现有 `binding_revisions` 数据通过回填脚本写入 strategy/params 默认值。

## 3. 对象关系（更新后）

```text
QARunEvidence
  -> Chunk
  -> ChunkRevision          (原 BindingRevision)
  -> ParseRevision
  -> DocumentVersion
  -> Document
```

| 对象 | 职责 |
| --- | --- |
| Document | 用户上传文件的业务身份 |
| DocumentVersion | 源文件版本 |
| ParseRevision | 解析版本，特定解析配置下的解析产物 |
| DocumentKbBinding | 文档与知识库的绑定关系，持有当前激活的 ChunkRevision |
| **ChunkRevision** | **某次将 ParseRevision 按特定分块策略物化到知识库的结果，承载策略配置和构建状态** |
| Chunk | 知识库检索的最小证据单元 |
| QARunEvidence | QA 运行命中的证据引用 |

## 4. 数据模型变更

### 4.1 chunk_revisions 表（原 binding_revisions）

```sql
-- 1. 重命名表
ALTER TABLE binding_revisions RENAME TO chunk_revisions;

-- 2. 重命名主键列
ALTER TABLE chunk_revisions RENAME COLUMN binding_revision_id TO chunk_revision_id;

-- 3. 新增分块策略列
ALTER TABLE chunk_revisions ADD COLUMN strategy VARCHAR(32) NOT NULL DEFAULT 'fixed_size';
ALTER TABLE chunk_revisions ADD COLUMN params JSONB NOT NULL DEFAULT '{}';

-- 4. 回填现有记录的 params
UPDATE chunk_revisions SET params = '{"chunk_size": 900, "chunk_overlap": 120}';
```

最终表结构：

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| chunk_revision_id | UUID | PK | 原 binding_revision_id |
| binding_id | UUID | FK → document_kb_bindings | 所属绑定 |
| knowledge_base_id | UUID | FK → knowledge_bases | |
| document_id | UUID | FK → documents | |
| document_version_id | UUID | FK → document_versions | |
| parse_revision_id | UUID | FK → parse_revisions | |
| strategy | VARCHAR(32) | NOT NULL, DEFAULT 'fixed_size' | 分块策略类型 |
| params | JSONB | NOT NULL, DEFAULT '{}' | 策略参数 |
| status | VARCHAR(16) | NOT NULL | building / active / retired / failed |
| chunk_count | INTEGER | DEFAULT 0 | |
| index_status | VARCHAR(16) | | |
| build_started_at | TIMESTAMPTZ | | |
| build_finished_at | TIMESTAMPTZ | | |
| activated_at | TIMESTAMPTZ | | |
| retired_at | TIMESTAMPTZ | | |
| deleted_at | TIMESTAMPTZ | | |
| created_by | UUID | | |
| created_at | TIMESTAMPTZ | NOT NULL | |

### 4.2 外键列重命名

| 表 | 旧列名 | 新列名 | 说明 |
|---|---|---|---|
| chunks | binding_revision_id | chunk_revision_id | FK → chunk_revisions |
| document_kb_bindings | active_binding_revision_id | active_chunk_revision_id | FK → chunk_revisions |

```sql
-- chunks 表
ALTER TABLE chunks RENAME COLUMN binding_revision_id TO chunk_revision_id;
-- FK 自动跟随重命名（PG 原生行为）

-- document_kb_bindings 表
ALTER TABLE document_kb_bindings RENAME COLUMN active_binding_revision_id TO active_chunk_revision_id;
```

### 4.3 document_kb_bindings 变更

```sql
-- 删除从未被 worker 使用的分块配置列
ALTER TABLE document_kb_bindings DROP COLUMN chunk_size;
ALTER TABLE document_kb_bindings DROP COLUMN chunk_overlap;
```

### 4.4 索引重命名

```sql
-- chunk_revisions 表索引
ALTER INDEX ix_binding_revisions_binding_id RENAME TO ix_chunk_revisions_binding_id;
ALTER INDEX ix_binding_revisions_knowledge_base_id RENAME TO ix_chunk_revisions_knowledge_base_id;
ALTER INDEX ix_binding_revisions_status RENAME TO ix_chunk_revisions_status;

-- chunks 表索引
ALTER INDEX ix_chunks_binding_revision_id RENAME TO ix_chunks_chunk_revision_id;

-- document_kb_bindings 表索引
ALTER INDEX ix_document_kb_bindings_active_binding_revision_id
  RENAME TO ix_document_kb_bindings_active_chunk_revision_id;
```

### 4.5 FK 约束重命名

```sql
ALTER TABLE chunk_revisions RENAME CONSTRAINT pk_binding_revisions TO pk_chunk_revisions;
ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_binding_id TO fk_chunk_revisions_binding_id;
ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_knowledge_base_id TO fk_chunk_revisions_knowledge_base_id;
ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_document_id TO fk_chunk_revisions_document_id;
ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_document_version_id TO fk_chunk_revisions_document_version_id;
ALTER TABLE chunk_revisions RENAME CONSTRAINT fk_binding_revisions_parse_revision_id TO fk_chunk_revisions_parse_revision_id;

ALTER TABLE chunks RENAME CONSTRAINT fk_chunks_binding_revision_id TO fk_chunks_chunk_revision_id;

ALTER TABLE document_kb_bindings RENAME CONSTRAINT fk_document_kb_bindings_active_binding_revision_id
  TO fk_document_kb_bindings_active_chunk_revision_id;
```

## 5. 内置策略定义

### 5.1 fixed_size（默认，当前行为）

```json
{
  "chunk_size": 900,
  "chunk_overlap": 120
}
```

### 5.2 semantic（预留）

```json
{
  "model": "all-MiniLM-L6-v2",
  "threshold": 0.8,
  "max_chunk_size": 1500
}
```

### 5.3 token_split（预留）

```json
{
  "max_tokens": 512,
  "overlap_tokens": 50,
  "tokenizer": "cl100k_base"
}
```

当前 Sprint 45 只实现 `fixed_size`，其他策略作为预留 schema。

## 6. 后端服务变更

### 6.1 标识符全量替换

以下标识符需要全量替换（731 处，48 个文件）：

**Python 后端**

| 旧标识符 | 新标识符 | 位置 |
|---|---|---|
| `binding_revisions` (表名) | `chunk_revisions` | tables.py, services, scripts |
| `binding_revision_id` (列名/变量) | `chunk_revision_id` | 全局 |
| `active_binding_revision_id` (列名/变量) | `active_chunk_revision_id` | binding_service, document_service |
| `BindingRevisionDTO` (类名) | `ChunkRevisionDTO` | schemas/binding.py |
| `activeBindingRevisionId` (DTO 字段) | `activeChunkRevisionId` | schemas/binding.py |
| `bindingRevisionStatus` (DTO 字段) | `chunkRevisionStatus` | schemas/binding.py |
| `bindingRevisionChunkCount` (DTO 字段) | `chunkRevisionChunkCount` | schemas/binding.py |
| `bindingRevisionVersionId` (DTO 字段) | `chunkRevisionVersionId` | schemas/binding.py |
| `bindingRevisionId` (DTO 字段) | `chunkRevisionId` | schemas/document.py, qa_run.py |
| `create_binding_revision()` | `create_chunk_revision()` | binding_service.py |
| `activate_binding_revision()` | `activate_chunk_revision()` | binding_service.py |
| `fail_binding_revision()` | `fail_chunk_revision()` | binding_service.py |
| `complete_binding_revision_build()` | `complete_chunk_revision_build()` | binding_service.py |
| `_to_binding_revision_dto()` | `_to_chunk_revision_dto()` | binding_service.py |
| `_attach_binding_revision_summary()` | `_attach_chunk_revision_summary()` | binding_service.py |
| `_read_active_binding_revision_id()` | `_read_active_chunk_revision_id()` | document_service.py |
| `_read_ingest_binding_revision()` | `_read_ingest_chunk_revision()` | document_service.py |

**TypeScript 前端**

| 旧标识符 | 新标识符 | 位置 |
|---|---|---|
| `activeBindingRevisionId` | `activeChunkRevisionId` | types/library.ts, pages |
| `bindingRevisionStatus` | `chunkRevisionStatus` | types/library.ts, pages |
| `bindingRevisionChunkCount` | `chunkRevisionChunkCount` | types/library.ts, pages |
| `bindingRevisionVersionId` | `chunkRevisionVersionId` | types/library.ts, pages |
| `bindingRevisionId` | `chunkRevisionId` | types/document.ts, qaRun.ts |
| `BINDING_REVISION_LABELS` | `CHUNK_REVISION_LABELS` | utils/threeLayerPresentation.ts |
| `BINDING_REVISION_VARIANTS` | `CHUNK_REVISION_VARIANTS` | utils/threeLayerPresentation.ts |
| `bindingRevisionStatusLabel()` | `chunkRevisionStatusLabel()` | utils/threeLayerPresentation.ts |
| `bindingRevisionStatusVariant()` | `chunkRevisionStatusVariant()` | utils/threeLayerPresentation.ts |

**前端 UI 文案**

| 旧文案 | 新文案 | 位置 |
|---|---|---|
| "Active BindingRevision" | "Active ChunkRevision" | P07_DocumentDetail.tsx |
| "当前 BindingRevision Chunks" | "当前 ChunkRevision Chunks" | P07_DocumentDetail.tsx |
| "BR {id}" | "CR {id}" | P10_QAHistory.tsx, qaRunAdapter.ts |

### 6.2 ChunkRevision 创建逻辑改造

`create_chunk_revision()` 需要新增 `strategy` 和 `params` 参数：

```python
def create_chunk_revision(
    conn,
    binding_id: str,
    knowledge_base_id: str,
    document_id: str,
    document_version_id: str,
    parse_revision_id: str,
    strategy: str = "fixed_size",
    params: dict | None = None,
    created_by: str | None = None,
) -> str:
    """创建一个新的 ChunkRevision，返回 chunk_revision_id。"""
    params = params or {}
    ...
```

### 6.3 初始绑定改造

`bind_documents_to_kb()` 改造：

```python
# 原：从 KB metadata 读 chunk_size/chunk_overlap，写入 binding
# 新：从 KB metadata 读默认策略，创建 ChunkRevision 时写入 strategy/params

default_strategy = kb_metadata.get("chunk_strategy", "fixed_size")
default_params = kb_metadata.get("chunk_params", {
    "chunk_size": kb_metadata.get("chunk_size", 900),
    "chunk_overlap": kb_metadata.get("chunk_overlap", 120),
})

chunk_revision_id = create_chunk_revision(
    ...,
    strategy=default_strategy,
    params=default_params,
)
```

### 6.4 Ingest Worker 改造

`run_ingest_job()` 需要从 ChunkRevision 读取分块策略，而不是硬编码默认值：

```python
# 原：parse_document(file_name, mime_type, source_bytes)  # 用默认 900/120
# 新：从 ChunkRevision 读取 strategy 和 params

chunk_revision = _read_ingest_chunk_revision(conn, job_id)
strategy = chunk_revision["strategy"]
params = chunk_revision["params"]

if strategy == "fixed_size":
    parsed_document = parse_document(
        file_name, mime_type, source_bytes,
        chunk_size=params.get("chunk_size", 900),
        chunk_overlap=params.get("chunk_overlap", 120),
    )
else:
    raise ValueError(f"Unsupported chunking strategy: {strategy}")
```

### 6.5 Rechunk API

新增 rechunk 端点：

```
POST /api/v1/knowledge-bases/{kb_id}/documents/{document_id}/rechunk
```

请求体：

```json
{
  "strategy": "fixed_size",
  "params": {
    "chunk_size": 600,
    "chunk_overlap": 100
  }
}
```

流程：

1. 校验 binding 存在且无 `building` 状态的 ChunkRevision。
2. 获取当前 active ChunkRevision 的 `parse_revision_id`（复用同一解析结果）。
3. 创建新 ChunkRevision（status = `building`），记录新 strategy + params。
4. 创建 `rechunk` 类型的 ingest job。
5. Worker 执行：按新策略重新分块，生成新 Chunk，走 build-then-activate 流程。
6. 成功后新 ChunkRevision 变为 `active`，旧的变为 `retired`。

### 6.6 新增 ingest job type

```sql
-- 在 migration 中添加 rechunk 类型（如果 job_type 有 CHECK 约束）
-- 或直接在代码中支持新类型
```

新增 `rechunk` job type，与 `reparse` 的区别：
- `reparse`：重新解析源文件，创建新 DocumentVersion + ParseRevision + ChunkRevision
- `rechunk`：不重新解析，复用现有 ParseRevision，只用新策略重新分块

## 7. 数据迁移与回填

### 7.1 Alembic 迁移脚本

迁移编号：`0028_rename_binding_revisions_to_chunk_revisions`

步骤：

1. RENAME TABLE `binding_revisions` → `chunk_revisions`
2. RENAME COLUMN `chunk_revisions.binding_revision_id` → `chunk_revision_id`
3. RENAME COLUMN `chunks.binding_revision_id` → `chunk_revision_id`
4. RENAME COLUMN `document_kb_bindings.active_binding_revision_id` → `active_chunk_revision_id`
5. ADD COLUMN `chunk_revisions.strategy` (VARCHAR(32), NOT NULL, DEFAULT 'fixed_size')
6. ADD COLUMN `chunk_revisions.params` (JSONB, NOT NULL, DEFAULT '{}')
7. UPDATE `chunk_revisions` SET params = '{"chunk_size": 900, "chunk_overlap": 120}'
8. DROP COLUMN `document_kb_bindings.chunk_size`
9. DROP COLUMN `document_kb_bindings.chunk_overlap`
10. 重命名所有 FK 约束和索引

### 7.2 回填脚本更新

更新 `backend/scripts/migrate_binding_revisions.py`：
- 函数名 `backfill_binding_revisions` → `backfill_chunk_revisions`
- 函数名 `link_active_binding_revisions` → `link_active_chunk_revisions`
- SQL 引用全部替换为新表名/列名

更新 `backend/scripts/migrate_chunks.py`：
- 函数名 `update_binding_revision_id` → `update_chunk_revision_id`
- SQL 引用替换

## 8. 测试变更

### 8.1 单元测试

| 文件 | 变更 |
|---|---|
| test_binding_lifecycle.py | 重命名所有函数调用和断言，新增 strategy/params 测试 |
| test_document_lifecycle.py | 重命名变量和断言 |
| test_deletion_impact_analysis.py | 更新 blocking_reasons 中的文案 |
| test_cross_resource_permission.py | 重命名变量 |

### 8.2 集成测试

| 文件 | 变更 |
|---|---|
| test_lifecycle_integration.py | 重命名函数调用和测试名 |
| test_data_migration.py | 重命名类和 SQL 引用 |

### 8.3 新增测试

- `test_rechunk_flow.py`：测试 rechunk 完整流程，包括同 ParseRevision 不同策略、build-then-activate、旧 revision retired。
- `test_chunk_revision_strategy_params.py`：测试 strategy/params 的读写和默认值。

### 8.4 前端测试

| 文件 | 变更 |
|---|---|
| threeLayerPresentation.test.ts | 重命名函数和常量 |
| b215-deletion-regression.spec.ts | 更新 locator regex |

## 9. Sprint 分期

### Sprint 45：后端全量改造

**范围：**

1. DB 迁移：RENAME TABLE/COLUMN + ADD strategy/params + DROP chunk_size/chunk_overlap
2. 后端标识符全量替换（Python 代码 + tests）
3. `create_chunk_revision()` 接入 strategy/params
4. `bind_documents_to_kb()` 从 KB metadata 读策略写入 ChunkRevision
5. `run_ingest_job()` 从 ChunkRevision 读策略传入 parse_document()
6. 新增 `rechunk` API 端点 + `rechunk` job type
7. 回填脚本更新
8. 全量测试通过

**Backlog 条目：**

| 编号 | 类型 | 标题 |
|---|---|---|
| B-225 | 技术 | DB 迁移：RENAME binding_revisions → chunk_revisions 并新增 strategy/params 列 |
| B-226 | 技术 | 后端标识符全量替换：binding_revision → chunk_revision |
| B-227 | 功能 | 改造 ChunkRevision 创建逻辑，接入 strategy 和 params 参数 |
| B-228 | 功能 | 改造初始绑定和 ingest worker，从 ChunkRevision 读取分块策略 |
| B-229 | 功能 | 实现 rechunk API 和 rechunk job type |
| B-230 | 技术 | 更新回填脚本适配新表名和列名 |
| B-231 | 测试 | 补齐 rechunk 流程和 strategy/params 单元测试，全量测试回归 |

### Sprint 46：前端 + 文档同步

**范围：**

1. 前端 TypeScript 类型全量替换
2. 前端页面文案更新
3. 前端 utils 函数重命名
4. P06 增加 rechunk 入口（选择策略 + 参数）
5. E2E 测试更新
6. 设计文档、接口文档、数据模型文档同步更新
7. OpenAPI 更新

**Backlog 条目：**

| 编号 | 类型 | 标题 |
|---|---|---|
| B-232 | 前端 | 前端 TypeScript 类型和 utils 全量替换 bindingRevision → chunkRevision |
| B-233 | 前端 | P06/P07/P10 页面文案和展示更新为 ChunkRevision |
| B-234 | 前端 | P06 增加 rechunk 入口，支持选择分块策略和参数 |
| B-235 | 测试 | 更新 E2E 测试和前端单元测试适配重命名 |
| B-236 | 文档 | 同步设计文档、接口文档、数据模型文档和 OpenAPI |
