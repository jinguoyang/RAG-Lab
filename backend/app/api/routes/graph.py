from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.common import PageResponse
from app.schemas.graph import (
    GraphCommunitySearchResponse,
    GraphEntitySearchResponse,
    GraphPathSearchResponse,
    GraphSnapshotDTO,
    GraphSupportingChunksResponse,
)
from app.services.graph_service import (
    get_graph_snapshot,
    list_graph_snapshots,
    list_supporting_chunks,
    search_graph_communities,
    search_graph_entities,
    search_graph_paths,
)

router = APIRouter(prefix="/knowledge-bases/{kb_id}", tags=["graph"])


@router.get("/graph-snapshots", response_model=PageResponse[GraphSnapshotDTO])
def read_graph_snapshots(
    kb_id: UUID,
    page_no: Annotated[int, Query(alias="pageNo", ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=100)] = 20,
    snapshot_status: Annotated[str | None, Query(alias="status")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> PageResponse[GraphSnapshotDTO]:
    """分页返回图快照元数据。"""
    response = list_graph_snapshots(session, current_user, kb_id, page_no, page_size, snapshot_status)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/graph-snapshots/{graph_snapshot_id}", response_model=GraphSnapshotDTO)
def read_graph_snapshot(
    kb_id: UUID,
    graph_snapshot_id: UUID,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> GraphSnapshotDTO:
    """返回单个图快照元数据。"""
    response = get_graph_snapshot(session, current_user, kb_id, graph_snapshot_id)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Graph snapshot not found.")
    return response


@router.get("/graph/entities", response_model=GraphEntitySearchResponse)
def read_graph_entities(
    kb_id: UUID,
    keyword: Annotated[str, Query(min_length=1)],
    graph_snapshot_id: Annotated[UUID | None, Query(alias="graphSnapshotId")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> GraphEntitySearchResponse:
    """搜索图实体摘要；正文证据仍需通过 supporting chunks 回落。"""
    response = search_graph_entities(session, current_user, kb_id, keyword, graph_snapshot_id, limit)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/graph/paths", response_model=GraphPathSearchResponse)
def read_graph_paths(
    kb_id: UUID,
    keyword: Annotated[str, Query(min_length=1)],
    graph_snapshot_id: Annotated[UUID | None, Query(alias="graphSnapshotId")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> GraphPathSearchResponse:
    """搜索关系路径摘要；正文证据仍需通过 supporting chunks 回落。"""
    response = search_graph_paths(session, current_user, kb_id, keyword, graph_snapshot_id, limit)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/graph/communities", response_model=GraphCommunitySearchResponse)
def read_graph_communities(
    kb_id: UUID,
    keyword: Annotated[str | None, Query(min_length=1)] = None,
    graph_snapshot_id: Annotated[UUID | None, Query(alias="graphSnapshotId")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> GraphCommunitySearchResponse:
    """搜索社区摘要；摘要不能直接作为最终 Evidence。"""
    response = search_graph_communities(session, current_user, kb_id, keyword, graph_snapshot_id, limit)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response


@router.get("/graph/supporting-chunks", response_model=GraphSupportingChunksResponse)
def read_graph_supporting_chunks(
    kb_id: UUID,
    graph_snapshot_id: Annotated[UUID, Query(alias="graphSnapshotId")],
    node_key: Annotated[str | None, Query(alias="nodeKey")] = None,
    relation_key: Annotated[str | None, Query(alias="relationKey")] = None,
    community_key: Annotated[str | None, Query(alias="communityKey")] = None,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> GraphSupportingChunksResponse:
    """返回图对象支撑 Chunk 引用摘要。"""
    response = list_supporting_chunks(
        session,
        current_user,
        kb_id,
        graph_snapshot_id,
        node_key,
        relation_key,
        community_key,
    )
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response
