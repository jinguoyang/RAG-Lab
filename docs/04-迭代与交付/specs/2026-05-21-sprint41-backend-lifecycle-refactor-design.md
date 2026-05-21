# Sprint 41 后端生命周期改造设计

本文档是 Sprint 41 后端生命周期改造的设计规范，涵盖文档解析、绑定生命周期、Chunk 管理、删除影响分析、QA 状态和 App Runtime 保护的实现方案。

## 1. 设计目标

- 打通文档库 ParseRevision 生命周期，支持解析产物管理。
- 改造知识库 BindingRevision 生命周期，支持版本切换和回滚。
- 实现 Chunk 生成和索引同步流程，仅 active Chunk 参与默认检索。
- 实现删除影响分析和强确认流程，保护线上服务。
- 支持 QA Evidence source_deleted 状态，保留历史记录。
- 增加 App Runtime 知识库启停保护和稳定错误码。

## 2. 核心对象关系

```text
Document
  -> DocumentVersion
       -> ParseRevision
            -> BindingRevision
                 -> Chunk / IndexSyncJob
                      -> QARun Evidence / Citation
```

## 3. Backlog 实现方案

### 3.1 B-202: 文档库上传和版本管理接入文件 hash 重复提醒

**目标：** 文档上传时检查文件 hash 重复，并将解析正文沉淀为 ParseRevision。

**实现方案：**

1. **文件 hash 重复检查**
   - 在 `document_service.py` 的上传逻辑中添加文件 hash 计算
   - 查询 `stored_files` 表检查是否存在相同 hash
   - 如果存在重复，返回提醒信息，允许用户选择是否继续上传

2. **ParseRevision 创建**
   - 文档解析完成后，创建 ParseRevision 记录
   - 保存解析正文到对象存储或数据库
   - 记录解析器信息和解析参数

**涉及文件：**
- `backend/app/services/document_service.py`
- `backend/app/schemas/document.py`

### 3.2 B-203: 改造知识库文档绑定模型，支持 BindingRevision 生命周期

**目标：** 支持 BindingRevision 的创建、激活、停用、删除。

**实现方案：**

1. **BindingRevision 生命周期**
   - 创建：绑定文档到知识库时创建 BindingRevision，状态为 `building`
   - 激活：构建成功后激活 BindingRevision，状态为 `active`
   - 停用：新版本激活后，旧版本状态为 `retired`
   - 删除：文档解绑或删除时，标记为 `deleted`

2. **DocumentKbBinding 改造**
   - 添加 `active_binding_revision_id` 字段
   - 支持查询当前激活的 BindingRevision

**涉及文件：**
- `backend/app/services/binding_service.py`
- `backend/app/schemas/binding.py`

### 3.3 B-204: 改造 Chunk 生成和索引同步流程

**目标：** 仅 active Chunk 参与默认检索。

**实现方案：**

1. **Chunk 状态管理**
   - 添加 `status` 字段：`building`、`active`、`retired`、`deleted`
   - 仅 `active` 状态的 Chunk 参与默认检索

2. **索引同步流程**
   - 构建 Chunk 时状态为 `building`
   - 索引同步成功后状态为 `active`
   - 版本切换后旧 Chunk 状态为 `retired`

**涉及文件：**
- `backend/app/services/document_service.py`
- `backend/app/services/chunk_payload.py`

### 3.4 B-205: 实现知识库绑定版本切换的先构建后激活流程

**目标：** 支持先构建后激活的版本切换流程。

**实现方案：**

1. **版本切换流程**
   - 创建新的 BindingRevision，状态为 `building`
   - 基于目标 ParseRevision 生成新的 Chunk
   - 写入向量库、全文索引和图结构等检索副本
   - 检索副本全部成功后，激活新版本
   - 旧版本状态为 `retired`

2. **失败处理**
   - 构建失败时，新 BindingRevision 状态为 `failed`
   - 旧 active BindingRevision 继续服务检索

**涉及文件：**
- `backend/app/services/binding_service.py`
- `backend/app/services/document_service.py`

### 3.5 B-206: 实现文档、文档版本、ParseRevision 删除影响分析和强确认流程

**目标：** 实现删除影响分析和强确认流程。

**实现方案：**

1. **删除影响分析**
   - 检查是否为文档库当前 active version
   - 检查是否存在 active BindingRevision
   - 检查是否存在 pending/running 任务
   - 汇总历史 QA 引用数量

2. **强确认流程**
   - 展示影响分析结果
   - 要求用户二次确认
   - 记录审计日志

3. **删除执行**
   - 删除或归档文档版本
   - 删除 ParseRevision 正文和记录
   - 清理 retired/disabled BindingRevision、Chunk 和索引副本
   - 更新 QA Evidence 状态为 `source_deleted`

**涉及文件：**
- `backend/app/services/document_service.py`
- `backend/app/services/cross_resource_permission.py`

### 3.6 B-207: QA Evidence 接入 source_deleted 状态

**目标：** 支持 QA Evidence source_deleted 状态。

**实现方案：**

1. **状态管理**
   - 添加 `source_status` 字段：`available`、`source_deleted`
   - 删除源文档时更新 Evidence 状态

2. **展示逻辑**
   - `available`：展示文档名、版本、页码或章节、命中片段
   - `source_deleted`：展示“引用文件已被清理”

**涉及文件：**
- `backend/app/services/qa_run_service.py`
- `backend/app/schemas/qa.py`

### 3.7 B-208: App Runtime 增加知识库启停保护和稳定错误码

**目标：** 增加知识库启停保护和稳定错误码。

**实现方案：**

1. **知识库启停保护**
   - 知识库 disabled 时，App Runtime 返回稳定错误
   - 不删除 App 和 Key

2. **稳定错误码**
   - 定义错误码：`KB_DISABLED`、`KB_NOT_FOUND`、`KB_BINDING_INVALID`
   - 返回友好的错误信息

**涉及文件：**
- `backend/app/services/app_runtime_service.py`
- `backend/app/schemas/app.py`

## 4. 数据流设计

### 4.1 文档上传流程

```text
用户上传文件
-> 计算文件 hash
-> 检查 hash 重复
-> 保存文件到对象存储
-> 创建 DocumentVersion
-> 触发解析任务
-> 解析完成创建 ParseRevision
-> 返回上传结果
```

### 4.2 知识库绑定流程

```text
用户绑定文档到知识库
-> 校验权限
-> 创建 DocumentKbBinding
-> 创建 BindingRevision (building)
-> 触发 Chunk 生成任务
-> 生成 Chunk 并写入索引
-> 激活 BindingRevision (active)
-> 更新 DocumentKbBinding.active_binding_revision_id
-> 返回绑定结果
```

### 4.3 版本切换流程

```text
用户切换文档版本
-> 校验权限
-> 创建新 BindingRevision (building)
-> 基于新 ParseRevision 生成 Chunk
-> 写入检索副本
-> 激活新 BindingRevision (active)
-> 旧 BindingRevision 状态为 retired
-> 旧 Chunk 状态为 retired
-> 异步清理旧检索副本
-> 返回切换结果
```

### 4.4 删除流程

```text
用户删除文档版本
-> 校验权限
-> 执行影响分析
-> 展示影响分析结果
-> 用户强确认
-> 删除 DocumentVersion
-> 删除 ParseRevision
-> 清理 BindingRevision、Chunk、索引副本
-> 更新 QA Evidence 状态
-> 记录审计日志
-> 返回删除结果
```

## 5. 错误处理

### 5.1 错误码定义

| 错误码 | 含义 | HTTP 状态码 |
| --- | --- | --- |
| `KB_DISABLED` | 知识库已禁用 | 403 |
| `KB_NOT_FOUND` | 知识库不存在 | 404 |
| `KB_BINDING_INVALID` | 绑定关系无效 | 400 |
| `VERSION_ACTIVE` | 版本正在使用中 | 409 |
| `TASK_RUNNING` | 任务正在运行 | 409 |
| `FILE_HASH_DUPLICATE` | 文件 hash 重复 | 409 |

### 5.2 错误处理策略

- 权限错误：返回 403 Forbidden
- 资源不存在：返回 404 Not Found
- 状态冲突：返回 409 Conflict
- 参数错误：返回 400 Bad Request

## 6. 测试策略

### 6.1 单元测试

- 测试每个服务的核心逻辑
- 测试权限校验
- 测试状态转换

### 6.2 集成测试

- 测试完整的业务流程
- 测试跨服务交互
- 测试数据一致性

### 6.3 测试覆盖目标

- 核心逻辑：100% 覆盖
- 边缘场景：90% 覆盖
- 错误处理：100% 覆盖

## 7. 验收标准

### 7.1 功能验收

- 文档上传时检查文件 hash 重复并创建 ParseRevision
- 支持 BindingRevision 生命周期管理
- 仅 active Chunk 参与默认检索
- 支持先构建后激活的版本切换流程
- 实现删除影响分析和强确认流程
- 支持 QA Evidence source_deleted 状态
- App Runtime 知识库启停保护正常

### 7.2 性能验收

- 文档上传响应时间 < 3 秒
- 版本切换响应时间 < 5 秒
- 删除操作响应时间 < 10 秒

### 7.3 安全验收

- 权限校验完整
- 审计日志记录完整
- 敏感操作需要二次确认

## 8. 风险与缓解

### 8.1 技术风险

- **风险：** 数据迁移可能导致数据不一致
- **缓解：** 充分测试，分步迁移，保留回滚能力

### 8.2 性能风险

- **风险：** 删除操作可能影响线上服务
- **缓解：** 异步处理，限制并发，监控性能

### 8.3 业务风险

- **风险：** 用户误删重要数据
- **缓解：** 强确认机制，审计日志，回收站功能

## 9. 后续迭代

- 实现自动清理策略
- 实现跨版本对比检索
- 实现高级 ParseRevision 管理
- 优化大规模数据删除性能