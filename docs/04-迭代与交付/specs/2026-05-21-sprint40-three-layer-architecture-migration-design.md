# Sprint 40 三层架构迁移设计

本文档是 Sprint 40 的设计规范，用于指导数据模型迁移、权限服务重构和历史数据回填工作。

## 1. 设计目标

- 实现三层架构模型的数据结构迁移
- 重构权限服务以支持三层角色映射
- 建立历史数据回填策略
- 确保迁移过程的数据完整性和系统稳定性

## 2. 核心原则

1. **一次性重构**：采用一次性重构方法，一次性修改所有相关表结构
2. **向后兼容**：允许破坏性变更，但需要完整的数据迁移
3. **数据完整性**：确保迁移过程中数据不丢失、不损坏
4. **可回滚性**：准备完整的回滚脚本，确保迁移失败时可恢复

## 3. 数据模型迁移设计

### 3.1 新增表结构

#### 3.1.1 `parse_revisions` 表

```sql
CREATE TABLE parse_revisions (
    parse_revision_id UUID PRIMARY KEY,
    document_version_id UUID NOT NULL REFERENCES document_versions(version_id),
    content_format VARCHAR(16) NOT NULL, -- markdown, text
    content_object_key VARCHAR(512), -- 对象存储路径
    content_text TEXT, -- 或直接存储文本
    content_hash VARCHAR(128),
    parser_name VARCHAR(64),
    parser_version VARCHAR(32),
    parse_options JSONB DEFAULT '{}',
    status VARCHAR(16) NOT NULL, -- parsing, completed, failed
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_by UUID,
    deleted_at TIMESTAMP WITH TIME ZONE,
    deleted_by UUID
);
```

#### 3.1.2 `binding_revisions` 表

```sql
CREATE TABLE binding_revisions (
    binding_revision_id UUID PRIMARY KEY,
    binding_id UUID NOT NULL REFERENCES document_kb_bindings(binding_id),
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(kb_id),
    document_id UUID NOT NULL REFERENCES documents(document_id),
    document_version_id UUID NOT NULL REFERENCES document_versions(version_id),
    parse_revision_id UUID NOT NULL REFERENCES parse_revisions(parse_revision_id),
    status VARCHAR(16) NOT NULL, -- building, active, retired, failed, deleted
    chunk_count INTEGER DEFAULT 0,
    index_status VARCHAR(16),
    build_started_at TIMESTAMP WITH TIME ZONE,
    build_finished_at TIMESTAMP WITH TIME ZONE,
    activated_at TIMESTAMP WITH TIME ZONE,
    retired_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

### 3.2 修改现有表结构

#### 3.2.1 `chunks` 表修改

```sql
-- 添加新字段
ALTER TABLE chunks ADD COLUMN binding_revision_id UUID REFERENCES binding_revisions(binding_revision_id);
ALTER TABLE chunks ADD COLUMN parse_revision_id UUID REFERENCES parse_revisions(parse_revision_id);
ALTER TABLE chunks ADD COLUMN document_version_id UUID REFERENCES document_versions(version_id);
ALTER TABLE chunks ADD COLUMN start_offset INTEGER;
ALTER TABLE chunks ADD COLUMN end_offset INTEGER;
ALTER TABLE chunks ADD COLUMN section_path VARCHAR(255);
ALTER TABLE chunks ADD COLUMN heading VARCHAR(255);
ALTER TABLE chunks ADD COLUMN summary TEXT;
ALTER TABLE chunks ADD COLUMN retired_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE chunks ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
```

#### 3.2.2 `document_kb_bindings` 表修改

```sql
-- 添加新字段
ALTER TABLE document_kb_bindings ADD COLUMN active_binding_revision_id UUID REFERENCES binding_revisions(binding_revision_id);
```

## 4. 权限服务重构设计

### 4.1 角色映射重构

#### 4.1.1 平台角色

| 角色 | 定位 |
| --- | --- |
| `platform_admin` | 超级管理员，可管理用户、用户组、资源、权限和审计 |
| `platform_user` | 普通用户，可登录平台，可创建被允许创建的资源 |

#### 4.1.2 文档库角色

| 角色 | 权限范围 |
| --- | --- |
| `library_owner` | 全部文档库权限；可转移 owner、删除或归档文档库、管理成员 |
| `library_manager` | 除转移 owner、删除整个文档库外的全部权限；可管理成员 |
| `library_editor` | 上传、更新、版本管理、绑定、归档或删除文档、下载 |
| `library_binder` | 查看、预览、下载、绑定到知识库 |
| `library_viewer` | 查看、预览、下载 |

#### 4.1.3 知识库角色

| 角色 | 权限范围 |
| --- | --- |
| `kb_owner` | 全部知识库权限；可转移 owner、删除或归档知识库、管理成员 |
| `kb_manager` | 除转移 owner、删除整个知识库外的全部权限；可管理成员、配置、文档绑定和应用 |
| `kb_editor` | 绑定文档、解绑、重建索引、管理配置、运行 QA、查看历史 |
| `kb_viewer` | 查看知识库、文档摘要、Chunk 摘要和 QA 历史 |
| `kb_qa_runner` | 运行 QA，查看自己的 QA 运行结果 |

#### 4.1.4 应用角色

| 角色 | 权限范围 |
| --- | --- |
| `app_owner` | 管理 App、Key、统计、调用记录；可转移 owner、删除或归档 App |
| `app_operator` | 管理 Key、查看调用记录、查看统计、试运行 |
| `app_viewer` | 查看统计和调用记录 |

### 4.2 权限码映射

#### 4.2.1 文档库权限码

| 权限码 | 控制对象 | 说明 |
| --- | --- | --- |
| `library.view` | DocumentLibrary | 查看文档库基础信息 |
| `library.member.manage` | DocumentLibrary | 管理文档库成员 |
| `library.document.read` | Document | 查看文档列表、详情和预览 |
| `library.document.download` | StoredFile | 下载源文件 |
| `library.document.create` | Document | 上传新文档 |
| `library.document.update` | Document | 修改文档名称、密级、状态等基础信息 |
| `library.document.delete` | Document | 删除、停用或归档文档 |
| `library.version.create` | DocumentVersion | 上传新版本 |
| `library.version.activate` | DocumentVersion | 切换文档库 active version |
| `library.version.delete` | DocumentVersion | 删除未被引用的版本 |
| `library.document.bind` | Document / DocumentVersion | 允许将文档版本绑定到知识库 |

#### 4.2.2 知识库权限码

| 权限码 | 控制对象 | 说明 |
| --- | --- | --- |
| `kb.view` | KnowledgeBase | 查看知识库基础信息 |
| `kb.manage` | KnowledgeBase | 修改基础信息、启停知识库 |
| `kb.member.manage` | KbMemberBinding | 管理知识库成员 |
| `kb.document.bind` | DocumentKbBinding | 将文档版本绑定到知识库 |
| `kb.document.unbind` | DocumentKbBinding | 解绑文档 |
| `kb.document.rebuild` | DocumentKbBinding / Chunk | 重建 Chunk 和检索副本 |
| `kb.document.read` | DocumentKbBinding | 查看知识库文档摘要和绑定状态 |
| `kb.chunk.read` | Chunk | 查看 Chunk 正文或详情 |
| `kb.config.manage` | ConfigRevision | 保存、验证和激活配置 |
| `kb.qa.run` | QARun | 发起 QA |
| `kb.qa.history.read` | QARun | 查看知识库 QA 历史 |
| `kb.qa.history.read_own` | QARun | 查看自己发起的 QA 运行结果 |
| `kb.evaluation.manage` | EvaluationSample | 管理评估样本 |
| `kb.app.manage` | RagApp | 创建、编辑、停用知识库下的智能应用 |

#### 4.2.3 应用权限码

| 权限码 | 控制对象 | 说明 |
| --- | --- | --- |
| `app.view` | RagApp | 查看 App 基础信息 |
| `app.manage` | RagApp | 编辑、停用、归档 App |
| `app.owner.transfer` | RagApp | 转移 App owner |
| `app.delete` | RagApp | 删除或归档 App |
| `app.key.manage` | AppApiKey | 创建、删除、轮换 API Key |
| `app.invocation.read` | AppInvocation | 查看调用记录 |
| `app.stats.read` | AppInvocation | 查看调用统计 |
| `app.runtime.test` | RagApp | 在管理端试运行 Runtime |

### 4.3 跨资源权限校验

```python
def check_cross_resource_permission(session, current_user, source_library_id, target_kb_id):
    """校验跨资源权限：绑定文档到知识库"""
    # 1. 校验源文档库权限
    library_permission = has_library_permission(
        session, current_user, "library.document.bind", source_library_id
    )
    
    # 2. 校验目标知识库权限
    kb_permission = has_kb_permission(
        session, current_user, target_kb_id, "kb.document.bind"
    )
    
    # 3. 两侧权限都满足才允许
    return library_permission and kb_permission
```

## 5. 历史数据回填策略

### 5.1 回填步骤

#### 5.1.1 创建 parse_revisions 记录

```sql
-- 为每个 document_version 创建 parse_revision 记录
INSERT INTO parse_revisions (
    parse_revision_id,
    document_version_id,
    content_format,
    content_text,
    content_hash,
    parser_name,
    parser_version,
    status,
    created_at
)
SELECT 
    gen_random_uuid(),
    version_id,
    'markdown', -- 或根据实际情况
    content, -- 从现有数据提取
    content_hash,
    'legacy_parser',
    '1.0',
    'completed',
    created_at
FROM document_versions;
```

#### 5.1.2 创建 binding_revisions 记录

```sql
-- 为每个 document_kb_binding 创建 binding_revision 记录
INSERT INTO binding_revisions (
    binding_revision_id,
    binding_id,
    knowledge_base_id,
    document_id,
    document_version_id,
    parse_revision_id,
    status,
    chunk_count,
    created_at
)
SELECT 
    gen_random_uuid(),
    binding_id,
    kb_id,
    document_id,
    version_id,
    (SELECT parse_revision_id FROM parse_revisions 
     WHERE document_version_id = db.version_id LIMIT 1),
    'active',
    chunk_count,
    created_at
FROM document_kb_bindings db;
```

#### 5.1.3 更新 chunks 表

```sql
-- 更新现有 chunks 表，添加新字段
UPDATE chunks 
SET 
    binding_revision_id = (
        SELECT binding_revision_id 
        FROM binding_revisions 
        WHERE binding_id = (
            SELECT binding_id 
            FROM document_kb_bindings 
            WHERE document_id = chunks.document_id 
            AND kb_id = chunks.kb_id 
            LIMIT 1
        )
    ),
    parse_revision_id = (
        SELECT parse_revision_id 
        FROM parse_revisions 
        WHERE document_version_id = chunks.version_id 
        LIMIT 1
    ),
    document_version_id = chunks.version_id;
```

### 5.2 回填验证

```sql
-- 验证 parse_revisions 数量
SELECT COUNT(*) FROM parse_revisions;

-- 验证 binding_revisions 数量
SELECT COUNT(*) FROM binding_revisions;

-- 验证 chunks 关联完整性
SELECT COUNT(*) FROM chunks 
WHERE binding_revision_id IS NULL 
OR parse_revision_id IS NULL 
OR document_version_id IS NULL;
```

## 6. 测试策略

### 6.1 单元测试

#### 6.1.1 权限服务测试

```python
# test_permission_service.py
def test_platform_admin_has_all_permissions():
    """测试平台管理员拥有所有权限"""
    
def test_library_owner_has_library_permissions():
    """测试文档库所有者拥有文档库权限"""
    
def test_kb_editor_has_kb_permissions():
    """测试知识库编辑者拥有知识库权限"""
    
def test_cross_resource_permission_check():
    """测试跨资源权限校验"""
    
def test_user_group_permission_union():
    """测试用户组权限并集"""
```

#### 6.1.2 数据迁移测试

```python
# test_data_migration.py
def test_parse_revisions_creation():
    """测试 parse_revisions 表创建"""
    
def test_binding_revisions_creation():
    """测试 binding_revisions 表创建"""
    
def test_chunks_table_migration():
    """测试 chunks 表迁移"""
    
def test_data_integrity_after_migration():
    """测试迁移后数据完整性"""
```

### 6.2 集成测试

```python
# test_e2e_migration.py
def test_document_upload_creates_parse_revision():
    """测试文档上传创建 parse_revision"""
    
def test_kb_binding_creates_binding_revision():
    """测试知识库绑定创建 binding_revision"""
    
def test_chunk_generation_with_new_structure():
    """测试新结构下的 chunk 生成"""
    
def test_permission_check_with_new_roles():
    """测试新角色下的权限检查"""
```

### 6.3 回归测试

```python
# test_regression.py
def test_existing_document_operations():
    """测试现有文档操作"""
    
def test_existing_kb_operations():
    """测试现有知识库操作"""
    
def test_existing_permission_checks():
    """测试现有权限检查"""
```

## 7. 风险评估和缓解措施

### 7.1 主要风险

#### 7.1.1 数据迁移失败

- **影响**：历史数据丢失或损坏
- **缓解措施**：
  - 迁移前备份数据库
  - 分步骤迁移，每步验证
  - 准备回滚脚本

#### 7.1.2 权限服务重构影响现有功能

- **影响**：用户无法访问资源
- **缓解措施**：
  - 保持现有权限检查逻辑
  - 逐步替换权限服务
  - 准备权限回滚方案

#### 7.1.3 性能下降

- **影响**：系统响应变慢
- **缓解措施**：
  - 优化数据库查询
  - 添加适当索引
  - 监控性能指标

#### 7.1.4 兼容性问题

- **影响**：现有功能异常
- **缓解措施**：
  - 充分的回归测试
  - 保持 API 接口兼容
  - 逐步迁移功能

### 7.2 缓解措施实施

#### 7.2.1 备份策略

```bash
# 迁移前备份
pg_dump -h localhost -U username -d database_name > backup_$(date +%Y%m%d_%H%M%S).sql

# 验证备份
pg_restore --list backup_*.sql
```

#### 7.2.2 回滚脚本

```sql
-- 回滚 parse_revisions 表
DROP TABLE IF EXISTS parse_revisions CASCADE;

-- 回滚 binding_revisions 表
DROP TABLE IF EXISTS binding_revisions CASCADE;

-- 回滚 chunks 表字段
ALTER TABLE chunks 
DROP COLUMN IF EXISTS binding_revision_id,
DROP COLUMN IF EXISTS parse_revision_id,
DROP COLUMN IF EXISTS document_version_id,
DROP COLUMN IF EXISTS start_offset,
DROP COLUMN IF EXISTS end_offset,
DROP COLUMN IF EXISTS section_path,
DROP COLUMN IF EXISTS heading,
DROP COLUMN IF EXISTS summary,
DROP COLUMN IF EXISTS retired_at,
DROP COLUMN IF EXISTS deleted_at;
```

#### 7.2.3 监控指标

- 数据库连接数
- 查询响应时间
- 错误率
- 用户访问量

## 8. 验收标准

### 8.1 数据模型验收

- [ ] `parse_revisions` 表创建成功
- [ ] `binding_revisions` 表创建成功
- [ ] `chunks` 表字段添加成功
- [ ] `document_kb_bindings` 表字段添加成功
- [ ] 数据完整性验证通过

### 8.2 权限服务验收

- [ ] 三层角色映射配置完成
- [ ] 权限码映射配置完成
- [ ] 跨资源权限校验实现完成
- [ ] 权限服务测试通过

### 8.3 历史数据回填验收

- [ ] `parse_revisions` 数据回填完成
- [ ] `binding_revisions` 数据回填完成
- [ ] `chunks` 数据更新完成
- [ ] 数据一致性验证通过

### 8.4 测试验收

- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 回归测试通过
- [ ] 性能测试通过

## 9. 实施计划

### 9.1 阶段 1：数据模型迁移

1. 创建 `parse_revisions` 表
2. 创建 `binding_revisions` 表
3. 修改 `chunks` 表结构
4. 修改 `document_kb_bindings` 表结构
5. 验证数据模型

### 9.2 阶段 2：权限服务重构

1. 配置三层角色映射
2. 配置权限码映射
3. 实现跨资源权限校验
4. 测试权限服务

### 9.3 阶段 3：历史数据回填

1. 回填 `parse_revisions` 数据
2. 回填 `binding_revisions` 数据
3. 更新 `chunks` 数据
4. 验证数据完整性

### 9.4 阶段 4：测试和验证

1. 执行单元测试
2. 执行集成测试
3. 执行回归测试
4. 性能测试和优化

## 10. 相关文档

- `docs/04-迭代与交付/specs/2026-05-20-permission-role-model-design.md`
- `docs/04-迭代与交付/specs/2026-05-21-document-version-parse-revision-deletion-design.md`
- `docs/04-迭代与交付/specs/2026-05-21-knowledge-base-chunk-management-design.md`
- `docs/04-迭代与交付/specs/2026-05-21-document-kb-app-architecture-briefing.md`