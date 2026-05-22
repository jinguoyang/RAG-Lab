from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUserResponse
from app.schemas.library_management import (
    AddLibraryMemberRequest,
    CreateLibraryRequest,
    LibraryDTO,
    LibraryDetailDTO,
    LibraryMemberDTO,
    LibraryPageResponse,
    UpdateLibraryMemberRequest,
    UpdateLibraryRequest,
)
from app.services.permission_service import (
    _user_id,
    check_library_owner_or_admin,
    has_library_access,
    library_visibility_condition,
)
from app.tables import document_kb_bindings, document_libraries, document_versions, documents, library_member_bindings


class LibraryNotFoundError(Exception):
    pass


class LibraryPermissionError(Exception):
    pass


class LibraryMemberNotFoundError(Exception):
    pass


class LibraryMemberConflictError(Exception):
    pass


def _to_library_dto(row, document_count: int = 0) -> LibraryDTO:
    return LibraryDTO(
        libraryId=str(row["library_id"]),
        ownerId=str(row["owner_id"]),
        name=row["name"],
        description=row.get("description"),
        visibility=row["visibility"],
        status=row["status"],
        documentCount=document_count,
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _count_library_documents(session: Session, library_id: UUID) -> int:
    return session.execute(
        select(func.count()).select_from(documents).where(
            documents.c.library_id == library_id,
            documents.c.deleted_at.is_(None),
        )
    ).scalar_one()


def create_library(
    session: Session,
    current_user: CurrentUserResponse,
    request: CreateLibraryRequest,
) -> LibraryDTO:
    actor_id = _user_id(current_user)
    library_id = uuid4()
    now = datetime.now(timezone.utc)

    session.execute(
        document_libraries.insert().values(
            library_id=library_id,
            owner_id=actor_id,
            name=request.name,
            description=request.description,
            visibility=request.visibility,
            status="active",
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
    )
    session.commit()

    row = session.execute(
        select(document_libraries).where(document_libraries.c.library_id == library_id)
    ).mappings().first()
    return _to_library_dto(row, document_count=0)


def list_libraries(
    session: Session,
    current_user: CurrentUserResponse,
    page_no: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
) -> LibraryPageResponse:
    visibility_cond = library_visibility_condition(current_user)

    base_query = select(document_libraries).where(visibility_cond)
    if keyword and keyword.strip():
        safe_keyword = keyword.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        base_query = base_query.where(document_libraries.c.name.ilike(f"%{safe_keyword}%", escape="\\"))

    total = session.execute(
        select(func.count()).select_from(base_query.subquery())
    ).scalar_one()

    offset = (page_no - 1) * page_size
    rows = session.execute(
        base_query
        .order_by(document_libraries.c.created_at.desc())
        .offset(offset)
        .limit(page_size)
    ).mappings().all()

    items = []
    for row in rows:
        doc_count = _count_library_documents(session, row["library_id"])
        items.append(_to_library_dto(row, document_count=doc_count))

    return LibraryPageResponse(
        items=items,
        total=total,
        pageNo=page_no,
        pageSize=page_size,
    )


def get_library_detail(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
) -> LibraryDetailDTO:
    row = session.execute(
        select(document_libraries).where(
            document_libraries.c.library_id == library_id,
            document_libraries.c.deleted_at.is_(None),
        )
    ).mappings().first()
    if row is None:
        raise LibraryNotFoundError
    if not has_library_access(
        session,
        current_user,
        permission_code="library.document.read",
        library_id=library_id,
        library_owner_id=UUID(str(row["owner_id"])),
    ):
        raise LibraryPermissionError

    doc_count = _count_library_documents(session, library_id)
    return LibraryDetailDTO(
        libraryId=str(row["library_id"]),
        ownerId=str(row["owner_id"]),
        name=row["name"],
        description=row.get("description"),
        visibility=row["visibility"],
        status=row["status"],
        documentCount=doc_count,
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def update_library(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
    request: UpdateLibraryRequest,
) -> LibraryDTO:
    if not check_library_owner_or_admin(session, current_user, library_id):
        raise LibraryPermissionError

    row = session.execute(
        select(document_libraries).where(
            document_libraries.c.library_id == library_id,
            document_libraries.c.deleted_at.is_(None),
        )
    ).mappings().first()
    if row is None:
        raise LibraryNotFoundError

    values: dict = {"updated_at": datetime.now(timezone.utc), "updated_by": _user_id(current_user)}
    if request.name is not None:
        values["name"] = request.name
    if request.description is not None:
        values["description"] = request.description
    if request.visibility is not None:
        values["visibility"] = request.visibility

    session.execute(
        update(document_libraries)
        .where(document_libraries.c.library_id == library_id)
        .values(**values)
    )
    session.commit()

    row = session.execute(
        select(document_libraries).where(document_libraries.c.library_id == library_id)
    ).mappings().first()
    doc_count = _count_library_documents(session, library_id)
    return _to_library_dto(row, document_count=doc_count)


def delete_library(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
) -> None:
    if not check_library_owner_or_admin(session, current_user, library_id):
        raise LibraryPermissionError

    row = session.execute(
        select(document_libraries).where(
            document_libraries.c.library_id == library_id,
            document_libraries.c.deleted_at.is_(None),
        )
    ).mappings().first()
    if row is None:
        raise LibraryNotFoundError

    now = datetime.now(timezone.utc)
    actor_id = _user_id(current_user)

    library_doc_ids = [
        doc_id
        for (doc_id,) in session.execute(
            select(documents.c.document_id).where(
                documents.c.library_id == library_id,
                documents.c.deleted_at.is_(None),
            )
        )
    ]

    if library_doc_ids:
        binding_rows = session.execute(
            select(document_kb_bindings).where(
                document_kb_bindings.c.document_id.in_(library_doc_ids),
                document_kb_bindings.c.status.in_(["pending", "processing", "active", "failed"]),
            )
        ).mappings().all()
        binding_version_ids = [row["version_id"] for row in binding_rows if row["version_id"]]
        if binding_version_ids:
            kb_doc_ids = [
                doc_id
                for (doc_id,) in session.execute(
                    select(document_versions.c.document_id).where(
                        document_versions.c.version_id.in_(binding_version_ids)
                    )
                )
            ]
            if kb_doc_ids:
                session.execute(
                    update(documents)
                    .where(documents.c.document_id.in_(kb_doc_ids), documents.c.deleted_at.is_(None))
                    .values(
                        status="archived",
                        deleted_at=now,
                        deleted_by=actor_id,
                        updated_at=now,
                        updated_by=actor_id,
                    )
                )
        if binding_rows:
            session.execute(
                update(document_kb_bindings)
                .where(document_kb_bindings.c.binding_id.in_([row["binding_id"] for row in binding_rows]))
                .values(status="disabled", updated_at=now, updated_by=actor_id)
            )

    # 级联软删除库内文档
    session.execute(
        update(documents)
        .where(
            documents.c.library_id == library_id,
            documents.c.deleted_at.is_(None),
        )
        .values(
            status="archived",
            deleted_at=now,
            deleted_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
    )

    # 软删除文档库
    session.execute(
        update(document_libraries)
        .where(document_libraries.c.library_id == library_id)
        .values(status="archived", deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
    )
    session.commit()


def list_library_members(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
) -> list[LibraryMemberDTO]:
    if not check_library_owner_or_admin(session, current_user, library_id):
        raise LibraryPermissionError

    rows = session.execute(
        select(library_member_bindings).where(
            library_member_bindings.c.library_id == library_id,
            library_member_bindings.c.status == "active",
        )
        .order_by(library_member_bindings.c.created_at.desc())
    ).mappings().all()

    return [
        LibraryMemberDTO(
            bindingId=str(row["binding_id"]),
            subjectType=row["subject_type"],
            subjectId=str(row["subject_id"]),
            permissionLevel=row["permission_level"],
            status=row["status"],
            createdAt=row["created_at"].isoformat(),
        )
        for row in rows
    ]


def add_library_member(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
    request: AddLibraryMemberRequest,
) -> LibraryMemberDTO:
    if not check_library_owner_or_admin(session, current_user, library_id):
        raise LibraryPermissionError

    # 检查库是否存在
    lib_row = session.execute(
        select(document_libraries).where(
            document_libraries.c.library_id == library_id,
            document_libraries.c.deleted_at.is_(None),
        )
    ).mappings().first()
    if lib_row is None:
        raise LibraryNotFoundError

    # 检查是否已有活跃绑定
    existing = session.execute(
        select(library_member_bindings).where(
            library_member_bindings.c.library_id == library_id,
            library_member_bindings.c.subject_type == request.subjectType,
            library_member_bindings.c.subject_id == UUID(request.subjectId),
            library_member_bindings.c.status == "active",
        )
    ).first()
    if existing is not None:
        raise LibraryMemberConflictError

    binding_id = uuid4()
    now = datetime.now(timezone.utc)
    actor_id = _user_id(current_user)

    session.execute(
        library_member_bindings.insert().values(
            binding_id=binding_id,
            library_id=library_id,
            subject_type=request.subjectType,
            subject_id=UUID(request.subjectId),
            permission_level=request.permissionLevel,
            status="active",
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
        )
    )
    session.commit()

    row = session.execute(
        select(library_member_bindings).where(library_member_bindings.c.binding_id == binding_id)
    ).mappings().first()
    return LibraryMemberDTO(
        bindingId=str(row["binding_id"]),
        subjectType=row["subject_type"],
        subjectId=str(row["subject_id"]),
        permissionLevel=row["permission_level"],
        status=row["status"],
        createdAt=row["created_at"].isoformat(),
    )


def update_library_member(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
    binding_id: UUID,
    request: UpdateLibraryMemberRequest,
) -> LibraryMemberDTO:
    if not check_library_owner_or_admin(session, current_user, library_id):
        raise LibraryPermissionError

    row = session.execute(
        select(library_member_bindings).where(
            library_member_bindings.c.binding_id == binding_id,
            library_member_bindings.c.library_id == library_id,
            library_member_bindings.c.status == "active",
        )
    ).mappings().first()
    if row is None:
        raise LibraryMemberNotFoundError

    session.execute(
        update(library_member_bindings)
        .where(library_member_bindings.c.binding_id == binding_id)
        .values(
            permission_level=request.permissionLevel,
            updated_at=datetime.now(timezone.utc),
            updated_by=_user_id(current_user),
        )
    )
    session.commit()

    row = session.execute(
        select(library_member_bindings).where(library_member_bindings.c.binding_id == binding_id)
    ).mappings().first()
    return LibraryMemberDTO(
        bindingId=str(row["binding_id"]),
        subjectType=row["subject_type"],
        subjectId=str(row["subject_id"]),
        permissionLevel=row["permission_level"],
        status=row["status"],
        createdAt=row["created_at"].isoformat(),
    )


def remove_library_member(
    session: Session,
    current_user: CurrentUserResponse,
    library_id: UUID,
    binding_id: UUID,
) -> None:
    if not check_library_owner_or_admin(session, current_user, library_id):
        raise LibraryPermissionError

    row = session.execute(
        select(library_member_bindings).where(
            library_member_bindings.c.binding_id == binding_id,
            library_member_bindings.c.library_id == library_id,
            library_member_bindings.c.status == "active",
        )
    ).first()
    if row is None:
        raise LibraryMemberNotFoundError

    session.execute(
        update(library_member_bindings)
        .where(library_member_bindings.c.binding_id == binding_id)
        .values(
            status="disabled",
            updated_at=datetime.now(timezone.utc),
            updated_by=_user_id(current_user),
        )
    )
    session.commit()
