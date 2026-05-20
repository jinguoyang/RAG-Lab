# E28 文档库功能实施计划

本文档是 E28 文档库功能的开发计划与设计依据，属于后续 Sprint 36 至 Sprint 38 的执行入口。当前目标是在现有知识库文档中心之外引入“我的文档库”，让用户先上传并预览个人文档，再按需绑定到一个或多个知识库执行切块、向量化和检索副本同步。

## 1. 关键假设

- PostgreSQL 继续作为业务真值中心，MinIO 只保存原始文件和预览中间产物。
- 个人文档库以 `owner_id` 作为归属边界，绑定到知识库后才产生知识库级 Chunk 和检索副本。
- 现有知识库文档中心接口和数据不做一次性强制迁移，E28 先支持新旧流程并行；历史数据迁移需在单独任务中评估。
- 前端新增 P15“我的文档库”和 P16“文档库详情”，现有 P06 知识库文档中心只增加“从文档库添加”的入口。
- 文档预览优先支持 PDF、Markdown、TXT 和 DOCX；Excel 预览、大文件断点续传和复杂版本管理不作为 P0 范围。
- 权限采用最小可验证边界：文档库 API 必须校验当前用户只能访问自己的文档；绑定知识库时仍校验目标知识库管理或文档上传权限。

## 2. 修改范围

- 数据模型：调整 `documents` 归属字段，新增 `document_kb_bindings` 和 `library_parse_jobs`。
- 接口设计：新增 `/api/v1/library/documents` 文档库接口族，保留现有 `/api/v1/knowledge-bases/{kbId}/documents` 接口族。
- 详细设计：把上传时文本提取与绑定后切块向量化拆成两个阶段。
- 前端页面：新增 P15、P16，并改造 P06 的文档选择入口。
- Sprint 文档：Sprint 36 交付基础模型、上传、预览和最小权限；Sprint 37 交付绑定与知识库入库；Sprint 38 交付增强、批量操作、测试和性能边界。

## 3. 不修改范围

- 不在 E28 中重写现有 QA、检索、RAG App Runtime 或 Provider 编排。
- 不把 MinIO、Milvus、OpenSearch 或 Neo4j 作为业务真值来源。
- 不一次性删除历史知识库文档中心链路。
- 不新增文件夹、标签、自定义元数据、云盘接入或内容寻址存储。

## 4. 数据设计

### 4.1 `documents`

E28 后 `documents` 表表示个人文档库中的文档主对象，关键字段为：

| 字段 | 说明 |
| --- | --- |
| `document_id` | 文档主键 |
| `owner_id` | 文档归属用户，引用 `users.user_id` |
| `name` | 文档名称 |
| `source_type` | 来源类型，例如 `upload` |
| `security_level` | 文档密级 |
| `status` | `active` / `disabled` / `archived` |
| `active_version_id` | 当前文本提取成功的版本 |
| `metadata` | 页数、预览摘要、解析器等扩展信息 |

`kb_id` 不再作为 `documents` 的必填字段；文档与知识库关系通过 `document_kb_bindings` 表表达。保留历史 `kb_id` 数据时，应在迁移中生成对应绑定记录或在兼容字段中保留只读来源，不能让同一事实同时由两个字段维护。

### 4.2 `document_versions`

`document_versions` 继续表示用户上传文件的版本与文本提取结果。上传后只负责原始文件保存、文本提取和预览数据生成，不直接生成知识库 Chunk。

### 4.3 `document_kb_bindings`

该表表达文档与知识库的多对多绑定关系，也是知识库级切块、向量化和副本同步的入口。

| 字段 | 说明 |
| --- | --- |
| `binding_id` | 主键 |
| `document_id` | 引用 `documents.document_id` |
| `kb_id` | 引用 `knowledge_bases.kb_id` |
| `version_id` | 本次绑定使用的文档版本 |
| `chunk_size` / `chunk_overlap` | 绑定级切块参数 |
| `status` | `pending` / `processing` / `active` / `failed` / `disabled` |
| `chunk_count` | 当前绑定产生的 Chunk 数 |
| `error_code` / `error_message` | 失败诊断 |
| `created_at` / `created_by` | 创建审计 |
| `updated_at` / `updated_by` | 修改审计 |

建议唯一约束：同一 `document_id + kb_id + version_id` 在未停用状态下只能存在一条有效绑定。

### 4.4 `library_parse_jobs`

该表只记录文档库上传后的文本提取和预览生成作业，不替代现有 `ingest_jobs`。绑定知识库后的切块、索引和图构建继续使用 `ingest_jobs`。

| 字段 | 说明 |
| --- | --- |
| `job_id` | 主键 |
| `document_id` | 文档 ID |
| `version_id` | 文档版本 ID |
| `job_type` | `extract_text` / `generate_preview` / `reparse_library` |
| `status` | `queued` / `running` / `success` / `failed` / `cancelled` |
| `progress` | 0-100 |
| `error_code` / `error_message` | 失败诊断 |

## 5. 接口设计

### 5.1 文档库接口

| 接口 | 方法 | 路径 | 权限边界 | 说明 |
| --- | --- | --- | --- | --- |
| 文档库列表 | GET | `/api/v1/library/documents` | 当前用户自己的文档 | 分页、搜索、状态过滤 |
| 上传文档 | POST | `/api/v1/library/documents` | 当前登录用户 | 保存文件，创建文档、版本和文本提取作业 |
| 文档详情 | GET | `/api/v1/library/documents/{documentId}` | 文档 owner | 返回元数据、版本、预览状态 |
| 文档使用情况 | GET | `/api/v1/library/documents/{documentId}/usage` | 文档 owner | 返回绑定知识库和绑定状态 |
| 文档停用 | PATCH | `/api/v1/library/documents/{documentId}` | 文档 owner | 修改名称、状态等基础字段 |
| 批量操作 | POST | `/api/v1/library/documents/batch-actions` | 文档 owner | 批量停用、批量重新解析和批量删除标记 |

### 5.2 知识库绑定接口

| 接口 | 方法 | 路径 | 权限边界 | 说明 |
| --- | --- | --- | --- | --- |
| 绑定文档 | POST | `/api/v1/knowledge-bases/{kbId}/library-bindings` | `kb.document.upload` 或 `kb.manage`，且文档 owner 为当前用户 | 创建绑定并触发切块入库 |
| 绑定列表 | GET | `/api/v1/knowledge-bases/{kbId}/library-bindings` | `kb.document.read` | 查看来自文档库的绑定文档 |
| 更新绑定配置 | PATCH | `/api/v1/knowledge-bases/{kbId}/library-bindings/{bindingId}` | `kb.document.upload` 或 `kb.manage` | 更新切块参数并触发重建 |
| 解绑文档 | DELETE | `/api/v1/knowledge-bases/{kbId}/library-bindings/{bindingId}` | `kb.document.upload` 或 `kb.manage` | 停用绑定并异步清理检索副本 |

## 6. Sprint 切分

| Sprint | 范围 | 验收重点 |
| --- | --- | --- |
| Sprint 36 | 数据模型迁移、文档库上传/列表/详情、文本提取作业、PDF/Markdown 预览、P15/P16 基础页、最小 owner 权限 | 上传后能看到个人文档和预览；未授权用户不能访问他人文档 |
| Sprint 37 | 文本预览 API、TXT/DOCX 预览、解析结果存储改造（parsed_chunks[]）、绑定/解绑 API、KB ingest 解析复用、P06 从文档库添加、文档删除级联清理、重试机制、文档使用情况 | 文档可绑定多个知识库；绑定后生成知识库级 Chunk 和检索副本；库侧解析结果被 KB 复用；删除和重试链路完整 |
| Sprint 38 | 权限码收口、批量操作、失败重试、测试覆盖 | 批量与异常路径可验证；端到端测试覆盖上传、预览、绑定和使用情况 |

> **Sprint 38 范围调整**：因需求变更，B-183（P02 统计卡片）和 B-184（大文件断点续传/超时重试）已取消，不再开发。

## 7. 验证方式

- 文档设计：运行 `git diff --check`，确认计划、待办、系统设计和 Sprint 文档无空白错误。
- 后端基础：在实现 Sprint 时运行 `cd backend; conda run -n rag-lab alembic upgrade head` 和 `cd backend; conda run -n rag-lab python -m compileall app`。
- 后端验收：随各 Sprint 新增 `backend/scripts/verify_library_*.py` 脚本，覆盖上传、CRUD、解析、绑定、权限和批量操作。
- 前端验收：在 `frontend` 下运行 `npm run build`、`npm run lint` 和文档库页面对应验证脚本。
- API 契约：运行 `cd backend; conda run -n rag-lab python scripts/export_openapi.py`，确认新增接口进入 OpenAPI。
