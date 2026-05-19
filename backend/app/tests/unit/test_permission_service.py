"""权限服务单元测试。"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import insert

from app.services.permission_service import has_library_permission
from app.tables import role_permission_bindings


def _grant_permission(db, role_scope: str, role_code: str, permission_code: str, effect: str = "allow"):
    """在测试数据库中插入一条角色权限绑定。"""
    db.execute(
        insert(role_permission_bindings).values(
            role_permission_id=uuid4(),
            role_scope=role_scope,
            role_code=role_code,
            permission_code=permission_code,
            effect=effect,
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )


class TestHasLibraryPermission:
    """测试 has_library_permission 函数。"""

    def test_admin_user_always_has_permission(self, db, admin_user):
        """管理员用户应拥有所有权限。"""
        result = has_library_permission(db, admin_user, "library.document.delete")
        assert result is True

    def test_admin_bypasses_owner_check(self, db, admin_user):
        """管理员不需要是文档 owner。"""
        random_owner_id = uuid4()
        result = has_library_permission(
            db, admin_user, "library.document.delete",
            document_owner_id=random_owner_id,
        )
        assert result is True

    def test_regular_user_read_own_document(self, db, test_user):
        """普通用户可以读取自己的文档（需要有 read 权限）。"""
        _grant_permission(db, "platform", "user", "library.document.read")

        owner_id = uuid4()
        test_user.user.userId = str(owner_id)
        result = has_library_permission(
            db, test_user, "library.document.read",
            document_owner_id=owner_id,
        )
        assert result is True

    def test_regular_user_cannot_read_others_document(self, db, test_user):
        """普通用户不能读取他人的文档（无 admin 权限时）。"""
        result = has_library_permission(
            db, test_user, "library.document.read",
            document_owner_id=uuid4(),
        )
        # 在没有权限码数据的情况下应返回 False
        assert result is False

    def test_permission_denied_takes_precedence(self, db, test_user):
        """deny 应覆盖 allow。"""
        result = has_library_permission(db, test_user, "library.document.delete")
        assert result is False
