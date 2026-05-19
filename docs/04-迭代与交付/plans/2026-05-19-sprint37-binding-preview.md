# Sprint 37 设计文档：文档库预览完善 + 知识库绑定

本文档是 Sprint 37 的详细设计，覆盖文档预览增强、文档与知识库绑定链路、删除级联和重试机制。

## 1. 设计决策摘要

| 决策 | 选择 | 理由 |
|---|---|---|
| 范围方案 | 平衡方案（8→11 项） | 补齐关键 gap，不过度扩展 |
| 删除语义 | 软删除 + 级联清理 | 自动解绑 + 异步清理 chunks/索引 |
| 文本预览 | API 返回 preview_text + 懒加载全文 | 默认 2000 字符，支持全文查看 |
| DOCX 预览 | mammoth.js 富格式渲染 | 保留段落、列表、表格等格式 |
| 分块参数 | 使用 KB 默认值 | 简化 UI 和 API，不暴露 chunk_size/chunk_overlap |
| 解析复用 | 库侧存完整 parsed_chunks，KB ingest 复用 | 避免重复解析同一文件 |
| 重试机制 | P16 支持解析重试 + 绑定重试；P06 仅重试 ingest | 分层职责清晰 |

## 2. 架构设计

### 2.1 绑定链路数据流

```
个人文档库 (Library)              绑定层 (Binding)              知识库 (KB)
┌─────────────────┐             ┌─────────────────┐         ┌─────────────────┐
│ documents       │             │ document_kb_    │         │ documents       │
│ (kb_id=NULL)    │ ──绑定──→   │ bindings        │ ──→     │ (kb_id=xxx)     │
│ stored_files    │             │ status: pending  │         │ document_       │
│ document_       │             │ → processing     │         │   versions      │
│   versions      │             │ → active/failed  │         │ ingest_jobs     │
│ library_parse_  │             └─────────────────┘         │ chunks + indexes│
│   jobs          │                                         └─────────────────┘
└─────────────────┘
  preview_text +                    复用 stored_files         复用 parsed_chunks
  parsed_chunks[]                   (不重新上传)              (跳过 parse_document)
```

**关键约束：**
- 文件不重复上传：绑定时 KB 侧 documents 的 source_file_id 指向 library 的 stored_files
- 复用现有 ingest pipeline：绑定后创建 ingest_jobs，触发 run_ingest_job() 全链路
- 多对多关系：一个文档可绑定多个 KB，每个 KB 独立维护 chunks 和索引

### 2.2 解析结果存储

库侧 `document_versions.metadata` 扩展存储完整解析结果：

```json
{
  "parser_name": "pdf",
  "parser_version": "1.0",
  "preview_text": "前 2000 字符纯文本...",
  "full_text_length": 15000,
  "parsed_chunks": [
    {
      "content": "chunk 文本",
      "token_count": 120,
      "section": "第一章",
      "page_no": 1,
      "start_offset": 0,
      "end_offset": 500
    }
  ]
}
```

KB ingest 复用逻辑：
1. 绑定时，ingest pipeline 检查库侧 document_versions.metadata 中是否存在 parsed_chunks
2. 如果存在，直接读取复用，跳过 parse_document() 调用
3. 如果不存在（历史数据或解析失败），回退到重新解析

### 2.3 绑定状态机

```
pending → processing → active
                   ↘ failed → processing (重试)
                       active → disabled (解绑)
```

- pending：绑定请求已创建，等待处理
- processing：ingest 任务执行中（分块→向量化→索引）
- active：绑定成功，文档已在 KB 中可用
- failed：ingest 失败，可通过重试回到 processing
- disabled：已解绑，chunks 和索引已清理

## 3. 接口设计

### 3.1 文本预览 API（新增）

| 接口 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 文本预览 | GET | `/api/v1/library/documents/{id}/text` | ?mode=preview（默认 2000 字符）/ full / chunks |

响应：
- mode=preview：`{ "text": "...", "truncated": true, "full_length": 15000 }`
- mode=full：`{ "text": "...完整文本..." }`
- mode=chunks：`{ "chunks": [...parsed_chunks数组...] }`

### 3.2 绑定 API（新增）

| 接口 | 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|---|
| 绑定文档 | POST | `/api/v1/knowledge-bases/{kbId}/library-bindings` | kb.document.upload 或 kb.manage + 文档 owner | 绑定并触发 ingest |
| 绑定列表 | GET | `/api/v1/knowledge-bases/{kbId}/library-bindings` | kb.document.read | 查看绑定文档 |
| 解绑文档 | DELETE | `/api/v1/knowledge-bases/{kbId}/library-bindings/{bindingId}` | kb.document.upload 或 kb.manage | 解绑并清理索引 |

**绑定请求体：**
```json
{
  "document_ids": ["doc-id-1", "doc-id-2"]
}
```

支持批量绑定多个文档，使用目标 KB 的默认 chunk_size 和 chunk_overlap。

### 3.3 文档使用情况 API（新增）

| 接口 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 使用情况 | GET | `/api/v1/library/documents/{id}/usage` | 返回绑定的 KB 列表及状态 |

### 3.4 文档删除 API（新增）

| 接口 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 删除文档 | DELETE | `/api/v1/library/documents/{id}` | 软删除 + 级联清理绑定 |

### 3.5 重试 API（新增）

| 接口 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 重试解析 | POST | `/api/v1/library/documents/{id}/parse-retry` | 重新触发 library_parse_jobs |
| 重试绑定 | POST | `/api/v1/knowledge-bases/{kbId}/library-bindings/{bindingId}/retry` | 重新触发 ingest_jobs |

## 4. 删除级联设计

DELETE /library/documents/{id} 执行流程：

1. 软删除文档：`documents.deleted_at = now(), deleted_by = user_id`
2. 查询所有活跃绑定：`document_kb_bindings WHERE status IN ('active', 'processing')`
3. 逐个解绑（复用现有 delete_document 逻辑）：
   - binding.status = 'disabled'
   - 调用现有 delete_document() 清理 KB 侧文档（软删除 documents、标记 chunks 为 deleted、创建 index_sync_jobs 清理 Milvus/OpenSearch/Neo4j）
4. 保留库侧 documents、library_parse_jobs 和 stored_files（审计和引用安全）

## 5. 重试机制设计

### P16 文档库详情页

| 场景 | 触发 | 行为 |
|---|---|---|
| 解析失败 | 用户点击"重试解析" | POST /library/documents/{id}/parse-retry → 重新调用 parse_document() → 更新 preview_text + parsed_chunks |
| 绑定失败 | 用户点击"重试绑定" | POST /kb/{kbId}/library-bindings/{bindingId}/retry → 重新触发 ingest_jobs → 复用 parsed_chunks |

### P06 知识库文档中心

| 场景 | 触发 | 行为 |
|---|---|---|
| ingest 失败 | 用户点击"重试" | 仅重试 ingest_jobs → 读取库侧 parsed_chunks → 重新 chunk→embed→index |

## 6. 前端设计

### 6.1 P16 文档详情页改造

- 预览区域改为默认调用 `GET /library/documents/{id}/text?mode=preview`
- 新增"查看全文"按钮，点击后懒加载 `?mode=full`
- DOCX 文件新增 mammoth.js 富格式预览模式
- 新增"使用情况"卡片，展示绑定的 KB 列表和状态
- 解析失败时显示"重试解析"按钮
- 绑定失败时显示"重试绑定"按钮

### 6.2 P06 知识库文档中心改造

- 新增"从文档库添加"按钮（与现有"上传"并列）
- 点击打开文档选择器 Modal：
  - 列出当前用户的库侧文档（已解析成功的）
  - 支持多选
  - 确认后调用 POST /kb/{kbId}/library-bindings
- 绑定失败的文档显示"重试"按钮

### 6.3 新增依赖

- `mammoth.js`：DOCX 转 HTML 渲染（~120KB）

## 7. 任务清单

| 编号 | 标题 | 优先级 | 预估 | 说明 |
|---|---|---|---|---|
| S37-000 | 文本预览 API | P0 | 0.5d | GET /library/documents/{id}/text，支持 preview/full/chunks 模式 |
| S37-001 | TXT 在线预览组件 | P1 | 0.5d | 基于文本预览 API，用 <pre> 渲染 |
| S37-002 | DOCX 在线预览（mammoth.js） | P1 | 1d | 安装 mammoth.js，DOCX→HTML 渲染 |
| S37-003 | 解析结果存储改造 | P0 | 1d | library_parse_jobs 存储完整 parsed_chunks[] |
| S37-004 | 绑定服务 + 绑定/解绑 API | P0 | 1.5d | POST/GET/DELETE library-bindings |
| S37-005 | KB ingest 解析复用 | P0 | 1d | ingest pipeline 读取库侧 parsed_chunks 跳过解析 |
| S37-006 | P06 从文档库添加 | P0 | 1.5d | 文档选择器 Modal + 批量绑定 |
| S37-007 | 文档删除 API（级联清理） | P0 | 1d | 软删除 + 自动解绑 + 异步清理索引 |
| S37-008 | 重试机制（解析重试 + 绑定重试） | P0 | 1d | P16 解析/绑定重试 + P06 ingest 重试 |
| S37-009 | 文档使用情况 API + P16 展示 | P1 | 0.5d | GET /library/documents/{id}/usage + 前端卡片 |
| S37-010 | 绑定链路验收脚本 | P1 | 0.5d | 覆盖绑定、解绑、删除级联、重试 |

**总预估：10d**

## 8. 范围边界

- 不支持 Excel 预览（P2，推迟到后续 Sprint）
- 不支持文档版本管理（扩展功能）
- 不涉及知识库中现有文档迁移（新旧流程并行）
- 不支持复杂的 Chunk 去重或合并策略
- 不完成完整权限码与角色映射收口（Sprint 38）
- 不支持批量删除（Sprint 38）
- 不支持 parse job 分页查询（Sprint 38）
- 不支持上传文件大小限制（Sprint 38）
- 不支持审计日志记录（Sprint 38）

## 9. 验证命令

- 数据库迁移：`cd backend && conda run -n rag-lab alembic upgrade head`
- 后端编译：`cd backend && conda run -n rag-lab python -m compileall app`
- 绑定链路验收：`cd backend && conda run -n rag-lab python scripts/verify_library_binding.py`（新增）
- 解析复用验收：`cd backend && conda run -n rag-lab python scripts/verify_parse_reuse.py`（新增）
- 删除级联验收：`cd backend && conda run -n rag-lab python scripts/verify_library_delete.py`（新增）
- 前端构建：`cd frontend && npm run build`
- 前端验证：浏览器打开 /library/:docId 和 /knowledge-bases/:kbId/documents
- OpenAPI 导出：`cd backend && conda run -n rag-lab python scripts/export_openapi.py`
- 文档空白检查：`git diff --check`
