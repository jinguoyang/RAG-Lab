"""library permissions and error_detail

Revision ID: 0018_library_perms
Revises: 0017_document_library
Create Date: 2026-05-19 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0018_library_perms"
down_revision: str | None = "0017_document_library"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. library_parse_jobs 新增 error_detail
    op.add_column(
        "library_parse_jobs",
        sa.Column("error_detail", postgresql.JSONB(), nullable=True),
    )

    # 2. 插入权限码
    op.execute("""
        INSERT INTO permissions (permission_id, permission_code, scope, name, description, status, created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'library.document.read', 'library', '文档库-查看', '查看文档库文档列表和详情', 'active', now(), now()),
            (gen_random_uuid(), 'library.document.create', 'library', '文档库-创建', '上传新文档到文档库', 'active', now(), now()),
            (gen_random_uuid(), 'library.document.update', 'library', '文档库-修改', '修改文档库文档元数据', 'active', now(), now()),
            (gen_random_uuid(), 'library.document.delete', 'library', '文档库-删除', '删除文档库文档', 'active', now(), now()),
            (gen_random_uuid(), 'library.document.admin', 'library', '文档库-管理', '管理所有用户的文档库文档', 'active', now(), now())
        ON CONFLICT DO NOTHING
    """)

    # 3. 平台管理员绑定 library.document.admin
    op.execute("""
        INSERT INTO role_permission_bindings (role_permission_id, role_scope, role_code, permission_code, effect, status, created_at, updated_at)
        SELECT gen_random_uuid(), 'platform', 'admin', 'library.document.admin', 'allow', 'active', now(), now()
        WHERE NOT EXISTS (
            SELECT 1 FROM role_permission_bindings
            WHERE role_scope = 'platform' AND role_code = 'admin' AND permission_code = 'library.document.admin'
        )
    """)

    # 4. 普通用户绑定 read + create
    op.execute("""
        INSERT INTO role_permission_bindings (role_permission_id, role_scope, role_code, permission_code, effect, status, created_at, updated_at)
        SELECT gen_random_uuid(), 'platform', role_code, perm_code, 'allow', 'active', now(), now()
        FROM (VALUES ('user'), ('editor')) AS roles(role_code)
        CROSS JOIN (VALUES ('library.document.read'), ('library.document.create')) AS perms(perm_code)
        WHERE NOT EXISTS (
            SELECT 1 FROM role_permission_bindings
            WHERE role_scope = 'platform' AND role_code = roles.role_code AND permission_code = perms.perm_code
        )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM role_permission_bindings WHERE permission_code LIKE 'library.document.%'
    """)
    op.execute("""
        DELETE FROM permissions WHERE permission_code LIKE 'library.document.%'
    """)
    op.drop_column("library_parse_jobs", "error_detail")
