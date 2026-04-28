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


class GraphQueryDiagnosticsDTO(BaseModel):
    """图查询诊断信息，供 P11 区分真实空结果和 Provider 降级。"""

    degraded: bool = False
    degradedReason: str | None = None
    provider: str = "graph"


class GraphPathDTO(BaseModel):
    """图关系路径摘要；正文证据必须继续通过 supporting chunks 回落。"""

    pathKey: str
    sourceEntity: GraphEntityDTO
    targetEntity: GraphEntityDTO
    relationType: str
    hopCount: int
    supportKeys: dict[str, str | None] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphPathSearchResponse(BaseModel):
    """关系路径查询响应。"""

    items: list[GraphPathDTO]
    graphSnapshotId: str | None
    diagnostics: GraphQueryDiagnosticsDTO = Field(default_factory=GraphQueryDiagnosticsDTO)


class GraphCommunityDTO(BaseModel):
    """图社区摘要；不能直接作为最终 Evidence。"""

    communityKey: str
    title: str
    summary: str
    entityCount: int | None = None
    supportKeys: dict[str, str | None] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphCommunitySearchResponse(BaseModel):
    """社区摘要查询响应。"""

    items: list[GraphCommunityDTO]
    graphSnapshotId: str | None
    diagnostics: GraphQueryDiagnosticsDTO = Field(default_factory=GraphQueryDiagnosticsDTO)


class GraphSupportingChunkDTO(BaseModel):
    """图对象回落后的授权 Chunk 摘要。"""

    chunkId: str
    documentId: str
    documentName: str
    chunkIndex: int
    contentPreview: str
    securityLevel: str
    refType: str
    metadata: dict[str, Any]


class GraphSupportingChunksResponse(BaseModel):
    """图支撑 Chunk 查询响应，后续接入权限裁剪后返回 filteredCount。"""

    items: list[GraphSupportingChunkDTO]
    filteredCount: int
