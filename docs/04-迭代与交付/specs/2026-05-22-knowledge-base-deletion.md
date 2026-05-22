# 知识库删除功能设计

## 概述

在现有知识库启用/停用功能基础上，增加删除功能。采用软删除模式，支持级联清理关联数据，前端采用 GitHub 风格的二次确认交互。

## 背景

当前知识库只有 `draft/active/disabled/archived` 状态流转和启用/停用操作，没有删除功能。用户无法清理不再需要的知识库，导致数据堆积。

## 前置条件（阻断删除的情况）

| 条件 | 说明 |
|------|------|
| 存在活跃 RAG 应用 | `rag_apps` 中有 `status='active'` 且 `deleted_at IS NULL` 的应用绑定到该 KB |
| 存在运行中的 ingest_job | `ingest_jobs` 中有 `status IN ('pending', 'processing')` 的任务 |

后端在校验失败时返回具体原因和关联数据列表，前端展示提示并引导用户先处理。

## 关联数据查询接口

### `GET /api/knowledge-bases/{kb_id}/delete-impact`

查询删除知识库会影响的数据范围，用于前端展示确认弹窗。

**响应：**

```json
{
  "kb_name": "我的知识库",
  "blockers": {
    "active_rag_apps": [
      { "app_id": "...", "name": "客服助手", "status": "active" }
    ],
    "running_jobs": [
      { "job_id": "...", "status": "processing" }
    ]
  },
  "cascade_data": {
    "bindings": 15,
    "kb_documents": 15,
    "chunks": 1280,
    "config_revisions": 3,
    "inactive_rag_apps": [
      { "app_id": "...", "name": "测试助手", "status": "disabled" }
    ],
    "kb_members": 5
  },
  "unaffected": {
    "library_documents": 10,
    "description": "文件库中的源文档不会被删除"
  }
}
```

- `blockers`：阻断条件，非空时不允许删除
- `cascade_data`：将被级联清理的数据统计
- `unaffected`：不受影响的数据说明

## 删除执行接口

### `DELETE /api/knowledge-bases/{kb_id}`

**请求体：**

```json
{
  "confirm_name": "我的知识库"
}
```

**校验逻辑：**

1. `confirm_name` 必须与知识库名称完全匹配（区分大小写）
2. 不能存在活跃 RAG 应用
3. 不能存在运行中的 ingest_job

**错误码：**

| HTTP Status | Error Code | 说明 |
|-------------|------------|------|
| 400 | `confirm_name_mismatch` | 名称不匹配 |
| 409 | `active_rag_apps_exist` | 存在活跃应用 |
| 409 | `running_jobs_exist` | 存在运行中任务 |

## 级联删除逻辑

采用软删除，事务内执行：

```
1. 校验前置条件
2. 软删除知识库本身
   - status = 'archived', deleted_at = now(), deleted_by = current_user
3. 处理 document_kb_bindings
   - 所有绑定该 KB 的记录标记 status = 'disabled'
4. 软删除 KB 侧文档副本
   - documents WHERE kb_id = :kb_id AND deleted_at IS NULL
   - status = 'archived', deleted_at = now()
5. 标记 chunks 为 deleted
   - chunks WHERE kb_id = :kb_id
   - status = 'deleted'
6. 更新 chunk_access_filters
   - chunk_status = 'deleted'
7. 物理删除 graph_chunk_refs
   - WHERE kb_id = :kb_id
8. 软删除 config_revisions
   - WHERE knowledge_base_id = :kb_id
9. 取消运行中的 ingest_jobs（理论上不应有，防御性处理）
   - status = 'cancelled'
10. 删除 kb_member_bindings
    - WHERE kb_id = :kb_id
11. 软删除停用/归档的 rag_apps
    - rag_apps WHERE kb_id = :kb_id AND status != 'active'
    - status = 'archived', deleted_at = now()
12. 创建异步索引清理任务
    - Milvus: 删除该 kb_id 下的所有向量
    - OpenSearch: 删除该 kb_id 下的所有文档
    - Neo4j: 删除该 kb_id 下的图谱节点
13. 创建 MinIO 文件清理任务
    - 清理 KB 侧 stored_files
```

**事务边界：** 步骤 1-11 在同一个数据库事务中执行。步骤 12-13 是异步任务创建，失败不影响删除事务，记录警告日志。

## 不受影响的数据

| 数据 | 原因 |
|------|------|
| 文件库 (document_libraries) | 独立实体，与 KB 无直接外键 |
| 文件库中的源文档 (documents.library_id) | 源文档独立存在，绑定关系通过 document_kb_bindings 断开 |
| 文件库成员关系 (library_member_bindings) | 独立于知识库 |
| 已归档的 RAG 应用的历史对话 (app_conversations) | 保留历史记录 |

## 前端交互设计

### 删除确认弹窗

触发位置：知识库详情页或设置页，与启用/停用按钮并列。

弹窗内容：

1. **标题**：删除知识库「{kb_name}」
2. **阻断提示**（如果有 blockers）：
   - 列出活跃的 RAG 应用名称，提示"请先停用或删除以下智能应用"
   - 列出运行中的任务，提示"请等待任务完成"
   - 删除按钮置灰
3. **影响范围展示**：
   - 将被删除的绑定文档数量
   - 将被删除的向量索引数量
   - 将被删除的管线配置数量
   - 将被级联删除的停用应用列表
4. **安全提示**：文件库中的源文档不会被删除
5. **确认输入框**：请输入知识库名称以确认删除
6. **按钮**：取消 / 删除知识库（输入名称匹配后才可点击）

### 交互流程

```
点击"删除知识库"
  → 调用 GET /delete-impact 获取关联数据
  → 弹窗展示
  → 用户输入知识库名称
  → 名称匹配后"删除知识库"按钮可点击
  → 点击删除
  → 调用 DELETE /api/knowledge-bases/{kb_id}
  → 成功：关闭弹窗，跳转到知识库列表页
  → 失败：展示错误信息
```

## 与现有功能的关系

| 现有功能 | 关系 |
|----------|------|
| 停用知识库 | 删除是比停用更彻底的操作，停用后仍可启用，删除不可逆 |
| 解绑文档 | 删除知识库会自动解绑所有文档，无需手动操作 |
| 删除文件库 | 文件库删除已有实现（cascade to KB bindings），与本功能独立 |
| 删除 RAG 应用 | 已有独立删除功能，删除 KB 时对停用应用做级联处理 |
