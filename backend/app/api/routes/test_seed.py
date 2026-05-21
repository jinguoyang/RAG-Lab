"""测试数据 Seed API，仅在 TEST_SEED_ENABLED=true 时启用。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db_session

router = APIRouter(prefix="/test", tags=["test"])


class SeedUser(BaseModel):
    username: str
    platform_role: str = "platform_user"


class SeedMember(BaseModel):
    username: str
    role: str


class SeedLibrary(BaseModel):
    name: str
    owner: str | None = None
    members: list[SeedMember] = []


class SeedKnowledgeBase(BaseModel):
    name: str
    library_name: str
    owner: str | None = None
    members: list[SeedMember] = []


class SeedPayload(BaseModel):
    users: list[SeedUser] = []
    libraries: list[SeedLibrary] = []
    knowledge_bases: list[SeedKnowledgeBase] = []


@router.post("/seed")
def seed_test_data(payload: SeedPayload, db: Session = Depends(get_db_session)):
    """批量创建测试前置数据。仅在 test_seed_enabled 时可用。"""
    settings = get_settings()
    if not settings.test_seed_enabled:
        raise HTTPException(status_code=404, detail="Not found")

    created = {"users": [], "libraries": [], "knowledge_bases": []}

    # Cache username -> user_id mapping for member lookups
    user_id_cache: dict[str, str] = {}

    for user in payload.users:
        row = db.execute(
            text(
                """
                INSERT INTO users (username, display_name, platform_role, security_level, status)
                VALUES (:username, :display_name, :role, 'public', 'active')
                ON CONFLICT (username) DO UPDATE SET platform_role = :role
                RETURNING user_id
                """
            ),
            {"username": user.username, "display_name": user.username, "role": user.platform_role},
        ).fetchone()
        db.flush()
        uid = str(row[0])
        user_id_cache[user.username] = uid
        created["users"].append({"username": user.username, "user_id": uid})

    for lib in payload.libraries:
        # Resolve owner: explicit owner field, or first member, or skip
        owner_name = lib.owner or (lib.members[0].username if lib.members else None)
        if not owner_name:
            continue
        owner_id = _resolve_user_id(db, owner_name, user_id_cache)
        if not owner_id:
            continue

        row = db.execute(
            text(
                """
                INSERT INTO document_libraries (name, owner_id, visibility, status)
                VALUES (:name, :owner_id, 'private', 'active')
                RETURNING library_id
                """
            ),
            {"name": lib.name, "owner_id": owner_id},
        ).fetchone()
        library_id = row[0]
        db.flush()

        for member in lib.members:
            member_id = _resolve_user_id(db, member.username, user_id_cache)
            if member_id:
                db.execute(
                    text(
                        """
                        INSERT INTO library_member_bindings
                            (library_id, subject_type, subject_id, permission_level, status)
                        VALUES (:library_id, 'user', :user_id, :permission_level, 'active')
                        """
                    ),
                    {"library_id": library_id, "user_id": member_id, "permission_level": member.role},
                )

        db.flush()
        created["libraries"].append({"name": lib.name, "library_id": str(library_id)})

    for kb in payload.knowledge_bases:
        lib_row = db.execute(
            text("SELECT library_id FROM document_libraries WHERE name = :name"),
            {"name": kb.library_name},
        ).fetchone()
        if not lib_row:
            continue

        # Resolve owner: explicit owner field, or first member, or skip
        owner_name = kb.owner or (kb.members[0].username if kb.members else None)
        if not owner_name:
            continue
        owner_id = _resolve_user_id(db, owner_name, user_id_cache)
        if not owner_id:
            continue

        row = db.execute(
            text(
                """
                INSERT INTO knowledge_bases
                    (name, owner_id, default_security_level,
                     sparse_index_enabled, graph_index_enabled,
                     sparse_required_for_activation, graph_required_for_activation,
                     status, metadata)
                VALUES (:name, :owner_id, 'public', false, false, false, false, 'active', '{}')
                RETURNING kb_id
                """
            ),
            {"name": kb.name, "owner_id": owner_id},
        ).fetchone()
        kb_id = row[0]
        db.flush()

        for member in kb.members:
            member_id = _resolve_user_id(db, member.username, user_id_cache)
            if member_id:
                db.execute(
                    text(
                        """
                        INSERT INTO kb_member_bindings
                            (kb_id, subject_type, subject_id, kb_role, status)
                        VALUES (:kb_id, 'user', :user_id, :kb_role, 'active')
                        """
                    ),
                    {"kb_id": kb_id, "user_id": member_id, "kb_role": member.role},
                )

        db.flush()
        created["knowledge_bases"].append({"name": kb.name, "kb_id": str(kb_id)})

    db.commit()
    return created


def _resolve_user_id(
    db: Session, username: str, cache: dict[str, str]
) -> str | None:
    """Look up a user_id from the cache or the database."""
    if username in cache:
        return cache[username]
    row = db.execute(
        text("SELECT user_id FROM users WHERE username = :username"),
        {"username": username},
    ).fetchone()
    if row:
        uid = str(row[0])
        cache[username] = uid
        return uid
    return None
