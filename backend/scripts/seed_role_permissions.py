"""Seed three-layer role-permission mappings.

Reads the ROLE_PERMISSIONS matrix and upserts rows into role_permission_bindings.
Idempotent: safe to run multiple times. Also ensures the required permission codes
exist in the permissions table and expands the role_scope check constraint to
allow 'library' and 'app' scopes.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import sqlalchemy as sa
from sqlalchemy import text

from app.core.database import get_engine

# ---------------------------------------------------------------------------
# Permission codes to ensure exist (code, scope, name)
# ---------------------------------------------------------------------------
NEW_PERMISSIONS: list[tuple[str, str, str]] = [
    # Library permissions
    ("library.view", "library", "查看文档库"),
    ("library.member.manage", "library", "管理文档库成员"),
    ("library.document.read", "library", "查看文档库文档"),
    ("library.document.download", "library", "下载文档库文档"),
    ("library.document.create", "library", "创建文档库文档"),
    ("library.document.update", "library", "更新文档库文档"),
    ("library.document.delete", "library", "删除文档库文档"),
    ("library.document.bind", "library", "绑定文档到知识库"),
    ("library.document.admin", "library", "文档库管理"),
    ("library.version.create", "library", "创建文档版本"),
    ("library.version.activate", "library", "激活文档版本"),
    ("library.version.delete", "library", "删除文档版本"),
    # KB permissions (new ones not in original migration)
    ("kb.document.bind", "kb", "绑定文档到知识库"),
    ("kb.document.unbind", "kb", "解绑文档"),
    ("kb.document.rebuild", "kb", "重建文档索引"),
    ("kb.qa.history.read_own", "kb", "查看自己的 QA 历史"),
    ("kb.app.manage", "kb", "管理知识库关联应用"),
    # App permissions
    ("app.view", "app", "查看应用"),
    ("app.manage", "app", "管理应用"),
    ("app.owner.transfer", "app", "转移应用所有权"),
    ("app.delete", "app", "删除应用"),
    ("app.key.manage", "app", "管理应用 API Key"),
    ("app.invocation.read", "app", "查看应用调用记录"),
    ("app.stats.read", "app", "查看应用统计"),
    ("app.runtime.test", "app", "应用运行时测试"),
]

# ---------------------------------------------------------------------------
# Role -> permission code mappings (from design spec)
# ---------------------------------------------------------------------------
ROLE_PERMISSIONS: dict[str, list[str]] = {
    # Platform roles
    "platform_admin": [],  # wildcard, handled specially
    "platform_user": [],  # basic login only
    # Library roles
    "library_owner": [
        "library.view",
        "library.member.manage",
        "library.document.read",
        "library.document.download",
        "library.document.create",
        "library.document.update",
        "library.document.delete",
        "library.version.create",
        "library.version.activate",
        "library.version.delete",
        "library.document.bind",
    ],
    "library_manager": [
        "library.view",
        "library.member.manage",
        "library.document.read",
        "library.document.download",
        "library.document.create",
        "library.document.update",
        "library.document.delete",
        "library.version.create",
        "library.version.activate",
        "library.version.delete",
        "library.document.bind",
    ],
    "library_editor": [
        "library.view",
        "library.document.read",
        "library.document.download",
        "library.document.create",
        "library.document.update",
        "library.document.delete",
        "library.version.create",
        "library.version.activate",
        "library.version.delete",
        "library.document.bind",
    ],
    "library_binder": [
        "library.view",
        "library.document.read",
        "library.document.download",
        "library.document.bind",
    ],
    "library_viewer": [
        "library.view",
        "library.document.read",
        "library.document.download",
    ],
    # KB roles
    "kb_owner": [
        "kb.view",
        "kb.manage",
        "kb.member.manage",
        "kb.document.bind",
        "kb.document.unbind",
        "kb.document.rebuild",
        "kb.document.read",
        "kb.chunk.read",
        "kb.config.manage",
        "kb.qa.run",
        "kb.qa.history.read",
        "kb.qa.history.read_own",
        "kb.evaluation.manage",
        "kb.app.manage",
    ],
    "kb_manager": [
        "kb.view",
        "kb.manage",
        "kb.member.manage",
        "kb.document.bind",
        "kb.document.unbind",
        "kb.document.rebuild",
        "kb.document.read",
        "kb.chunk.read",
        "kb.config.manage",
        "kb.qa.run",
        "kb.qa.history.read",
        "kb.qa.history.read_own",
        "kb.evaluation.manage",
        "kb.app.manage",
    ],
    "kb_editor": [
        "kb.view",
        "kb.document.bind",
        "kb.document.unbind",
        "kb.document.rebuild",
        "kb.document.read",
        "kb.chunk.read",
        "kb.config.manage",
        "kb.qa.run",
        "kb.qa.history.read",
    ],
    "kb_viewer": [
        "kb.view",
        "kb.document.read",
        "kb.chunk.read",
        "kb.qa.history.read",
    ],
    "kb_qa_runner": [
        "kb.view",
        "kb.qa.run",
        "kb.qa.history.read_own",
    ],
    # App roles
    "app_owner": [
        "app.view",
        "app.manage",
        "app.owner.transfer",
        "app.delete",
        "app.key.manage",
        "app.invocation.read",
        "app.stats.read",
        "app.runtime.test",
    ],
    "app_operator": [
        "app.view",
        "app.key.manage",
        "app.invocation.read",
        "app.stats.read",
        "app.runtime.test",
    ],
    "app_viewer": [
        "app.view",
        "app.invocation.read",
        "app.stats.read",
    ],
}

THREE_LAYER_SCOPES = ("platform", "library", "kb", "app")


def _determine_role_scope(role_code: str) -> str:
    """Derive role_scope from role_code prefix."""
    if role_code.startswith("platform_"):
        return "platform"
    if role_code.startswith("library_"):
        return "library"
    if role_code.startswith("kb_"):
        return "kb"
    if role_code.startswith("app_"):
        return "app"
    raise ValueError(f"Cannot determine scope for role_code: {role_code}")


def expand_role_scope_constraint(engine: sa.Engine) -> None:
    """Expand the role_scope check constraint to allow 'library' and 'app'."""
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE role_permission_bindings
            DROP CONSTRAINT IF EXISTS ck_role_permission_bindings_role_scope
        """))
        conn.execute(text("""
            ALTER TABLE role_permission_bindings
            ADD CONSTRAINT ck_role_permission_bindings_role_scope
            CHECK (role_scope IN ('platform', 'kb', 'library', 'app'))
        """))
        print("  [OK] role_scope constraint expanded to include 'library', 'app'")


def expand_permissions_scope_constraint(engine: sa.Engine) -> None:
    """Expand the permissions scope check constraint to allow 'app'."""
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE permissions
            DROP CONSTRAINT IF EXISTS ck_permissions_scope
        """))
        conn.execute(text("""
            ALTER TABLE permissions
            ADD CONSTRAINT ck_permissions_scope
            CHECK (scope IN ('platform', 'kb', 'document', 'chunk', 'library', 'app'))
        """))
        print("  [OK] permissions scope constraint expanded to include 'app'")


def ensure_permissions(engine: sa.Engine) -> None:
    """Insert permission codes that don't yet exist."""
    with engine.begin() as conn:
        for code, scope, name in NEW_PERMISSIONS:
            conn.execute(
                text("""
                    INSERT INTO permissions (permission_id, permission_code, scope, name, status, created_at, updated_at)
                    VALUES (gen_random_uuid(), :code, :scope, :name, 'active', now(), now())
                    ON CONFLICT (permission_code) DO NOTHING
                """),
                {"code": code, "scope": scope, "name": name},
            )
        print(f"  [OK] Ensured {len(NEW_PERMISSIONS)} permission codes exist")


def clear_three_layer_bindings(engine: sa.Engine) -> None:
    """Delete existing role_permission_bindings for three-layer role scopes."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                DELETE FROM role_permission_bindings
                WHERE role_scope = ANY(:scopes)
            """),
            {"scopes": list(THREE_LAYER_SCOPES)},
        )
        print(f"  [OK] Cleared {result.rowcount} existing bindings for scopes {THREE_LAYER_SCOPES}")


def insert_bindings(engine: sa.Engine) -> None:
    """Insert all role-permission bindings from the matrix."""
    count = 0
    with engine.begin() as conn:
        # Collect all permission codes for platform_admin wildcard
        all_codes = conn.execute(
            text("SELECT permission_code FROM permissions WHERE status = 'active'")
        ).scalars().all()

        for role_code, permission_codes in ROLE_PERMISSIONS.items():
            role_scope = _determine_role_scope(role_code)
            codes_to_bind = all_codes if role_code == "platform_admin" else permission_codes

            for permission_code in codes_to_bind:
                conn.execute(
                    text("""
                        INSERT INTO role_permission_bindings (
                            role_permission_id, role_scope, role_code,
                            permission_code, effect, status, created_at, updated_at
                        )
                        VALUES (
                            md5(:role_scope || ':' || :role_code || ':' || :permission_code)::uuid,
                            :role_scope,
                            :role_code,
                            :permission_code,
                            'allow',
                            'active',
                            now(),
                            now()
                        )
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "role_scope": role_scope,
                        "role_code": role_code,
                        "permission_code": permission_code,
                    },
                )
                count += 1

    print(f"  [OK] Inserted {count} role-permission bindings")


def verify(engine: sa.Engine) -> None:
    """Print summary of seeded data."""
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT role_scope, role_code, COUNT(*) AS perm_count
            FROM role_permission_bindings
            WHERE status = 'active'
              AND role_scope = ANY(:scopes)
            GROUP BY role_scope, role_code
            ORDER BY role_scope, role_code
        """), {"scopes": list(THREE_LAYER_SCOPES)}).fetchall()

    print("\n  Summary of role_permission_bindings:")
    print(f"  {'scope':<12} {'role_code':<20} {'permissions':>10}")
    print(f"  {'-'*12} {'-'*20} {'-'*10}")
    for scope, role_code, perm_count in rows:
        print(f"  {scope:<12} {role_code:<20} {perm_count:>10}")


def main() -> None:
    """Seed three-layer role-permission mappings."""
    print("=== Seed Role Permissions ===\n")

    engine = get_engine()

    print("[1/6] Expanding role_scope constraint...")
    expand_role_scope_constraint(engine)

    print("[2/6] Expanding permissions scope constraint...")
    expand_permissions_scope_constraint(engine)

    print("[3/6] Ensuring permission codes exist...")
    ensure_permissions(engine)

    print("[4/6] Clearing existing three-layer bindings...")
    clear_three_layer_bindings(engine)

    print("[5/6] Inserting role-permission bindings...")
    insert_bindings(engine)

    print("[6/6] Verifying...")
    verify(engine)

    print("\nDone.")


if __name__ == "__main__":
    main()
