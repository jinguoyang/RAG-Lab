from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.knowledge_base import KnowledgeBaseCreateRequest, KnowledgeBaseDTO
from app.services.knowledge_base_service import (
    create_knowledge_base,
    get_knowledge_base,
    list_knowledge_bases,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.get("", response_model=PageResponse[KnowledgeBaseDTO])
def read_knowledge_bases(
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    keyword: str | None = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[KnowledgeBaseDTO]:
    """分页返回当前开发用户可见的知识库列表。"""
    return list_knowledge_bases(session, current_user, page_no, page_size, keyword)


@router.post("", response_model=KnowledgeBaseDTO, status_code=status.HTTP_201_CREATED)
def create_knowledge_base_endpoint(
    request: KnowledgeBaseCreateRequest,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> KnowledgeBaseDTO:
    """创建知识库基础记录，供 E1 平台工作台联调使用。"""
    return create_knowledge_base(session, current_user, request)


@router.get("/{kb_id}", response_model=KnowledgeBaseDTO)
def read_knowledge_base(
    kb_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> KnowledgeBaseDTO:
    """返回单个知识库详情；不可见资源按不存在处理。"""
    knowledge_base = get_knowledge_base(session, current_user, kb_id)
    if knowledge_base is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found.",
        )
    return knowledge_base
