# 移除文档库可见性配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 `document_libraries.visibility` 字段及相关逻辑，简化权限模型为"所有者 + 成员绑定"。

**Architecture:** 删除 visibility 列及其在 schema/service/UI 中的所有引用。权限服务简化为：平台管理员/library.document.admin/所有者自动通过，其余用户查 `library_member_bindings` 表。新建 migration 0030 删除列、约束和索引。

**Tech Stack:** Python/FastAPI/SQLAlchemy, React/TypeScript, Alembic migrations

---

## File Structure

| Layer | File | Change |
|-------|------|--------|
| DB Migration | `backend/migrations/versions/0030_drop_library_visibility.py` | **Create** — drop column, constraint, index |
| DB Model | `backend/app/tables.py:179` | **Modify** — remove `visibility` column |
| Schema | `backend/app/schemas/library_management.py` | **Modify** — remove `visibility` from 4 classes |
| Permission | `backend/app/services/permission_service.py:516-712` | **Modify** — simplify `has_library_access()` and `library_visibility_condition()` |
| Library Mgmt | `backend/app/services/library_management_service.py` | **Modify** — remove visibility from DTO mapping, create, list, detail, update |
| Library Doc | `backend/app/services/library_service.py` | **Modify** — remove visibility from `_ensure_library_access`, `_ensure_owner`, `create_library_upload`, `list_library_documents` |
| Binding | `backend/app/services/binding_service.py:202-242` | **Modify** — remove visibility from `_ensure_library_owner` |
| API Route | `backend/app/api/routes/library_management.py` | **No change** — passes through to service |
| Test Seed | `backend/app/api/routes/test_seed.py:84` | **Modify** — remove `visibility` from INSERT |
| Verify | `backend/scripts/verify_library_review_fixes.py:77` | **Modify** — update assertion message |
| FE Types | `frontend/src/app/types/library.ts:5,35` | **Modify** — remove `LibraryVisibility` type and field |
| FE Service | `frontend/src/app/services/libraryService.ts:350-366` | **Modify** — remove `visibility` from create/update params |
| FE Page | `frontend/src/app/pages/P17_LibraryManagement.tsx` | **Modify** — remove visibility UI (badge, radio, column) |
| FE Page | `frontend/src/app/pages/P18_LibraryDocuments.tsx:30-40,277-299` | **Modify** — remove visibility badge and conditional member button |

---

### Task 1: 新建 migration 0030 删除 visibility 列

**Files:**
- Create: `backend/migrations/versions/0030_drop_library_visibility.py`

- [ ] **Step 1: 编写 migration 文件**

```python
"""drop library visibility column

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-22
"""
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_document_libraries_visibility_status", table_name="document_libraries")
    op.drop_constraint("ck_document_libraries_visibility", "document_libraries", type_="check")
    op.drop_column("document_libraries", "visibility")


def downgrade() -> None:
    op.add_column(
        "document_libraries",
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default=sa.text("'personal'")),
    )
    op.create_check_constraint(
        "ck_document_libraries_visibility",
        "document_libraries",
        "visibility IN ('public', 'personal', 'partial')",
    )
    op.create_index(
        "idx_document_libraries_visibility_status",
        "document_libraries",
        ["visibility", "status"],
    )
```

- [ ] **Step 2: 修复 downgrade 中缺少的 import**

在文件顶部补充 `import sqlalchemy as sa`，确保 downgrade 函数可用。

- [ ] **Step 3: 验证 migration 语法**

Run: `python -c "import backend.migrations.versions.0030_drop_library_visibility"`
Expected: 无 import 错误

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/versions/0030_drop_library_visibility.py
git commit -m "feat: add migration 0030 to drop library visibility column"
```

---

### Task 2: 删除后端 tables.py 中的 visibility 列定义

**Files:**
- Modify: `backend/app/tables.py:179`

- [ ] **Step 1: 删除 visibility 列**

删除第 179 行：
```python
sa.Column("visibility", sa.String(length=16), nullable=False),
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/tables.py
git commit -m "refactor: remove visibility column from document_libraries table definition"
```

---

### Task 3: 删除后端 schema 中的 visibility 字段

**Files:**
- Modify: `backend/app/schemas/library_management.py`

- [ ] **Step 1: 从 LibraryDTO 删除 visibility**

删除第 23 行 `visibility: str`

- [ ] **Step 2: 从 LibraryDetailDTO 删除 visibility**

删除第 37 行 `visibility: str`

- [ ] **Step 3: 从 CreateLibraryRequest 删除 visibility**

删除第 49 行 `visibility: Literal["public", "personal", "partial"] = "personal"`

- [ ] **Step 4: 从 UpdateLibraryRequest 删除 visibility**

删除第 57 行 `visibility: Literal["public", "personal", "partial"] | None = None`

- [ ] **Step 5: 检查 Literal 是否仍有引用**

`Literal` 仅被 `LibraryRole` 使用（第 6 行），确认无需删除 import。

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/library_management.py
git commit -m "refactor: remove visibility from library management schemas"
```

---

### Task 4: 简化 permission_service.py 中的 visibility 权限逻辑

**Files:**
- Modify: `backend/app/services/permission_service.py:516-712`

这是核心任务。需要修改两个函数并删除 visibility 参数。

- [ ] **Step 1: 修改 `has_library_access()` — 删除 `library_visibility` 参数**

将函数签名从：
```python
def has_library_access(
    session: Session,
    current_user: CurrentUserResponse,
    permission_code: str,
    library_id: UUID | None = None,
    library_owner_id: UUID | None = None,
    library_visibility: str | None = None,
) -> bool:
```
改为：
```python
def has_library_access(
    session: Session,
    current_user: CurrentUserResponse,
    permission_code: str,
    library_id: UUID | None = None,
    library_owner_id: UUID | None = None,
) -> bool:
```

- [ ] **Step 2: 简化 `has_library_access()` 函数体**

将第 606-640 行（`# 需要 library_id 和 visibility 来做进一步判断` 之后的全部逻辑）替换为：

```python
    # 需要 library_id 来查成员绑定
    if library_id is None:
        # 没有库信息时，回退到平台角色权限检查
        if permission_code in platform_denied:
            return False
        return permission_code in platform_allowed

    # 查 library_member_bindings
    group_ids = _active_group_ids(session, user_id)
    levels = _library_member_permission_levels(session, library_id, user_id, group_ids)

    granted_permissions: set[str] = set()
    if "read_only" in levels or "library_viewer" in levels:
        granted_permissions |= _READ_ONLY_PERMISSIONS
    if "library_binder" in levels:
        granted_permissions |= _BINDER_PERMISSIONS
    if "document_manage" in levels or "library_editor" in levels:
        granted_permissions |= _EDITOR_PERMISSIONS
    if "library_manager" in levels:
        granted_permissions |= _MANAGE_PERMISSIONS

    if permission_code in platform_denied:
        return False
    return permission_code in granted_permissions
```

- [ ] **Step 3: 更新 `has_library_access()` 的 docstring**

将 docstring 中的规则 4-6 替换为：
```
    4. 查 library_member_bindings，按角色授予对应权限
```

- [ ] **Step 4: 修改 `library_visibility_condition()` — 删除 visibility 依赖**

将函数体（第 682-712 行）替换为：

```python
    user_id = _user_id(current_user)
    active_group_ids = (
        select(user_group_members.c.group_id)
        .where(
            user_group_members.c.user_id == user_id,
            user_group_members.c.status == "active",
        )
        .scalar_subquery()
    )
    member_exists = exists(
        select(library_member_bindings.c.binding_id).where(
            library_member_bindings.c.library_id == document_libraries.c.library_id,
            library_member_bindings.c.status == "active",
            or_(
                and_(
                    library_member_bindings.c.subject_type == "user",
                    library_member_bindings.c.subject_id == user_id,
                ),
                and_(
                    library_member_bindings.c.subject_type == "group",
                    library_member_bindings.c.subject_id.in_(active_group_ids),
                ),
            ),
        )
    )
    return (document_libraries.c.deleted_at.is_(None)) & (
        (document_libraries.c.owner_id == user_id)
        | member_exists
        | (current_user.user.platformRole == "platform_admin")
    )
```

- [ ] **Step 5: 更新 `library_visibility_condition()` 的 docstring**

```
    可见规则：
    - 库未软删除
    - 且满足以下之一：
      a. 当前用户是库所有者
      b. 当前用户在 library_member_bindings 中
      c. 平台管理员
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/permission_service.py
git commit -m "refactor: simplify library access to owner + member bindings only"
```

---

### Task 5: 清理 library_management_service.py 中的 visibility 引用

**Files:**
- Modify: `backend/app/services/library_management_service.py`

- [ ] **Step 1: 从 `_to_library_dto()` 删除 visibility**

删除第 49 行 `visibility=row["visibility"],`

- [ ] **Step 2: 从 `create_library()` 删除 visibility**

删除第 81 行 `visibility=request.visibility,`

- [ ] **Step 3: 从 `list_libraries()` 更新 import**

第 22 行 import 中删除 `library_visibility_condition`（如果不再使用）。但 `list_libraries()` 第 104 行仍在调用它，所以保留 import，只需确认函数签名已更新（Task 4 已处理）。

- [ ] **Step 4: 从 `get_library_detail()` 删除 visibility 参数**

将第 149-156 行的 `has_library_access` 调用从：
```python
    if not has_library_access(
        session,
        current_user,
        permission_code="library.document.read",
        library_id=library_id,
        library_owner_id=UUID(str(row["owner_id"])),
        library_visibility=row["visibility"],
    ):
```
改为：
```python
    if not has_library_access(
        session,
        current_user,
        permission_code="library.document.read",
        library_id=library_id,
        library_owner_id=UUID(str(row["owner_id"])),
    ):
```

同时删除第 165 行 `visibility=row["visibility"],`

- [ ] **Step 5: 从 `update_library()` 删除 visibility 处理**

删除第 196-197 行：
```python
    if request.visibility is not None:
        values["visibility"] = request.visibility
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/library_management_service.py
git commit -m "refactor: remove visibility from library management service"
```

---

### Task 6: 清理 library_service.py 中的 visibility 引用

**Files:**
- Modify: `backend/app/services/library_service.py`

- [ ] **Step 1: 简化 `_ensure_library_access()`**

将第 86-93 行的 `has_library_access` 调用从：
```python
    if not has_library_access(
        session,
        current_user,
        permission_code=permission_code,
        library_id=library_id,
        library_owner_id=UUID(str(lib_row["owner_id"])),
        library_visibility=lib_row["visibility"],
    ):
```
改为：
```python
    if not has_library_access(
        session,
        current_user,
        permission_code=permission_code,
        library_id=library_id,
        library_owner_id=UUID(str(lib_row["owner_id"])),
    ):
```

- [ ] **Step 2: 简化 `_ensure_owner()`**

将第 264-291 行替换为：
```python
    # 获取文档库信息
    library_owner_id = None
    library_id = row.get("library_id")
    if library_id:
        lib_row = session.execute(
            select(document_libraries.c.owner_id).where(
                document_libraries.c.library_id == library_id,
                document_libraries.c.deleted_at.is_(None),
            )
        ).mappings().first()
        if lib_row:
            library_owner_id = UUID(str(lib_row["owner_id"]))

    # 回退：如果没有 library_id，使用 owner_id
    if library_owner_id is None:
        owner_id = row.get("owner_id")
        if owner_id:
            library_owner_id = UUID(str(owner_id))

    if not has_library_access(
        session, current_user, permission_code,
        library_id=UUID(str(library_id)) if library_id else None,
        library_owner_id=library_owner_id,
    ):
        raise LibraryPermissionError
```

- [ ] **Step 3: 从 `create_library_upload()` 删除 visibility**

将第 337 行 `visibility="personal",` 删除。

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/library_service.py
git commit -m "refactor: remove visibility from library document service"
```

---

### Task 7: 清理 binding_service.py 中的 visibility 引用

**Files:**
- Modify: `backend/app/services/binding_service.py:231-238`

- [ ] **Step 1: 简化 `_ensure_library_owner()` 中的 has_library_access 调用**

将第 231-238 行从：
```python
        if not has_library_access(
            session,
            current_user,
            permission_code="library.document.read",
            library_id=library_uuid,
            library_owner_id=UUID(str(lib_row["owner_id"])),
            library_visibility=lib_row["visibility"],
        ):
```
改为：
```python
        if not has_library_access(
            session,
            current_user,
            permission_code="library.document.read",
            library_id=library_uuid,
            library_owner_id=UUID(str(lib_row["owner_id"])),
        ):
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/binding_service.py
git commit -m "refactor: remove visibility from binding service"
```

---

### Task 8: 清理 test_seed.py 和 verify 脚本

**Files:**
- Modify: `backend/app/api/routes/test_seed.py:84`
- Modify: `backend/scripts/verify_library_review_fixes.py:77`

- [ ] **Step 1: 从 test_seed 删除 visibility**

将第 83-86 行从：
```sql
INSERT INTO document_libraries (name, owner_id, visibility, status)
VALUES (:name, :owner_id, 'private', 'active')
```
改为：
```sql
INSERT INTO document_libraries (name, owner_id, status)
VALUES (:name, :owner_id, 'active')
```

- [ ] **Step 2: 更新 verify 脚本断言**

将第 77 行的断言消息从 `"get_library_detail must enforce library visibility/read access."` 改为 `"get_library_detail must enforce library read access."`

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/routes/test_seed.py backend/scripts/verify_library_review_fixes.py
git commit -m "refactor: remove visibility from test seed and verify script"
```

---

### Task 9: 删除前端 LibraryVisibility 类型

**Files:**
- Modify: `frontend/src/app/types/library.ts:5,35`

- [ ] **Step 1: 删除 LibraryVisibility 类型**

删除第 5 行：
```typescript
export type LibraryVisibility = "public" | "personal" | "partial";
```

- [ ] **Step 2: 从 LibraryDTO 删除 visibility 字段**

删除第 35 行：
```typescript
  visibility: LibraryVisibility;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/types/library.ts
git commit -m "refactor: remove LibraryVisibility type from frontend"
```

---

### Task 10: 清理前端 libraryService.ts

**Files:**
- Modify: `frontend/src/app/services/libraryService.ts:350-366`

- [ ] **Step 1: 从 createLibrary 删除 visibility**

将第 350-356 行从：
```typescript
export async function createLibrary(body: {
  name: string;
  description?: string;
  visibility: "public" | "personal" | "partial";
}): Promise<LibraryDTO> {
  return apiPostJson<LibraryDTO>("/library", body);
}
```
改为：
```typescript
export async function createLibrary(body: {
  name: string;
  description?: string;
}): Promise<LibraryDTO> {
  return apiPostJson<LibraryDTO>("/library", body);
}
```

- [ ] **Step 2: 从 updateLibrary 删除 visibility**

将第 362-366 行从：
```typescript
export async function updateLibrary(
  libraryId: string,
  body: { name?: string; description?: string; visibility?: string },
): Promise<LibraryDTO> {
```
改为：
```typescript
export async function updateLibrary(
  libraryId: string,
  body: { name?: string; description?: string },
): Promise<LibraryDTO> {
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/services/libraryService.ts
git commit -m "refactor: remove visibility from frontend library service"
```

---

### Task 11: 清理 P17_LibraryManagement.tsx 中的可见性 UI

**Files:**
- Modify: `frontend/src/app/pages/P17_LibraryManagement.tsx`

- [ ] **Step 1: 删除 import 中的 LibraryVisibility**

第 17 行从 `import type { LibraryDTO, LibraryVisibility } from "../types/library"` 改为 `import type { LibraryDTO } from "../types/library"`

- [ ] **Step 2: 删除 visibilityLabel、visibilityVariant、currentRoleLabel 函数**

删除第 21-35 行（三个函数）。

- [ ] **Step 3: 删除 formVisibility 状态**

删除第 56 行 `const [formVisibility, setFormVisibility] = useState<LibraryVisibility>("personal");`

- [ ] **Step 4: 从 openCreateDrawer 删除 formVisibility 重置**

删除第 89 行 `setFormVisibility("personal");`

- [ ] **Step 5: 从 openEditDrawer 删除 formVisibility 设置**

删除第 97 行 `setFormVisibility(lib.visibility);`

- [ ] **Step 6: 从 handleSubmit 删除 visibility 参数**

第 109-113 行删除 `visibility: formVisibility,`
第 116-120 行删除 `visibility: formVisibility,`

- [ ] **Step 7: 删除表格中的"可见性"列**

删除第 208 行 `<TableHead>可见性</TableHead>`
删除第 231-235 行的可见性 Badge 渲染

- [ ] **Step 8: 删除"我的角色"列**

删除第 209 行 `<TableHead>我的角色</TableHead>`
删除第 236-238 行的角色 Badge 渲染（依赖 visibility 的 `currentRoleLabel`）

- [ ] **Step 9: 删除抽屉中的可见性选择器**

删除第 357-388 行的整个可见性 radio group 区块。

- [ ] **Step 10: Commit**

```bash
git add frontend/src/app/pages/P17_LibraryManagement.tsx
git commit -m "refactor: remove visibility UI from library management page"
```

---

### Task 12: 清理 P18_LibraryDocuments.tsx 中的可见性 UI

**Files:**
- Modify: `frontend/src/app/pages/P18_LibraryDocuments.tsx`

- [ ] **Step 1: 删除 visibilityLabel 和 visibilityVariant 函数**

删除第 30-40 行（两个函数）。

- [ ] **Step 2: 删除条件渲染的"成员管理"按钮**

将第 277-281 行从：
```tsx
{library?.visibility === "partial" && (
  <Button variant="secondary" onClick={() => navigate(`/library/${libraryId}/members`)}>
    <Users className="w-4 h-4 mr-2" /> 成员管理
  </Button>
)}
```
改为始终显示成员管理按钮（所有者可管理成员）：
```tsx
<Button variant="secondary" onClick={() => navigate(`/library/${libraryId}/members`)}>
  <Users className="w-4 h-4 mr-2" /> 成员管理
</Button>
```

- [ ] **Step 3: 删除信息栏中的 visibility Badge**

将第 294-299 行从：
```tsx
<div className="flex flex-wrap items-center gap-3 rounded-lg border border-border-cream bg-ivory px-4 py-3 text-sm">
  <Badge variant={visibilityVariant(library.visibility)}>{visibilityLabel(library.visibility)}</Badge>
  <span className="text-stone-gray">{library.documentCount} 个文档</span>
  <span className="text-stone-gray">最近更新 {new Date(library.updatedAt).toLocaleString("zh-CN")}</span>
</div>
```
改为：
```tsx
<div className="flex flex-wrap items-center gap-3 rounded-lg border border-border-cream bg-ivory px-4 py-3 text-sm">
  <span className="text-stone-gray">{library.documentCount} 个文档</span>
  <span className="text-stone-gray">最近更新 {new Date(library.updatedAt).toLocaleString("zh-CN")}</span>
</div>
```

- [ ] **Step 4: 清理未使用的 import**

如果 `Badge` 仅被 visibility 使用，删除其 import。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/pages/P18_LibraryDocuments.tsx
git commit -m "refactor: remove visibility UI from library documents page"
```

---

### Task 13: 后端测试验证

- [ ] **Step 1: 运行后端单元测试**

Run: `cd backend && python -m pytest app/tests/ -x -q`
Expected: 全部通过

- [ ] **Step 2: 运行后端类型检查（如有 mypy 配置）**

Run: `cd backend && python -m mypy app/services/ --ignore-missing-imports`
Expected: 无 visibility 相关错误

- [ ] **Step 3: 验证 import 无循环依赖**

Run: `cd backend && python -c "from app.services.permission_service import has_library_access, library_visibility_condition"`
Expected: 无错误

---

### Task 14: 前端构建验证

- [ ] **Step 1: 运行 TypeScript 类型检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 无 visibility 相关类型错误

- [ ] **Step 2: 运行前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功

---

### Task 15: 更新 OpenAPI 文档

- [ ] **Step 1: 重新生成 openapi.json**

Run 后端服务并导出最新 OpenAPI spec，或手动从 `docs/06-发布与运维/openapi.json` 中删除所有 `visibility` 字段引用。

- [ ] **Step 2: Commit**

```bash
git add docs/06-发布与运维/openapi.json
git commit -m "docs: remove visibility from OpenAPI spec"
```
