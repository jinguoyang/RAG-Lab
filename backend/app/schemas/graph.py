from typing import Any

from pydantic import BaseModel, Field


class GraphSnapshotDTO(BaseModel):
    """图快照元数据 DTO，不包含 Neo4j 中的完整图结构。"""

    graphSnapshotId: str
    kbId: str
    status: str
    sourceScope: dict[str, Any]
    neo4jGraphKey: str | None
    staleReason: str | None
    staleAt: str | None
    entityCount: int | None
    relationCount: int | None
    communityCount: int | None
    jobId: str | None
    errorMessage: str | None
    createdAt: str
    updatedAt: str


class GraphEntityDTO(BaseModel):
    """图实体搜索结果摘要，正文展示必须继续查询 supporting chunks。"""

    entityKey: str | None = None
    name: str
    type: str | None = None
    aliases: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEntitySearchResponse(BaseModel):
    """实体搜索响应，返回实际使用的图快照 ID。"""

    items: list[GraphEntityDTO]
    graphSnapshotId: str | None


class GraphSupportingChunkDTO(BaseModel):
    """图对象回落 Chunk 摘要；当前尚未包含 Chunk 正文真值。"""

    chunkId: str
    refType: str
    metadata: dict[str, Any]


class GraphSupportingChunksResponse(BaseModel):
    """图支撑 Chunk 查询响应，后续接入权限裁剪后返回 filteredCount。"""

    items: list[GraphSupportingChunkDTO]
    filteredCount: int
