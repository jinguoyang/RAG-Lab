# Epic 9 Graph Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Epic 9 (`B-043` to `B-046`) with graph snapshot diagnostics, graph paths/communities, authorized supporting Chunk fallback, P11 real API integration, and stale diagnostics.

**Architecture:** PostgreSQL remains the business truth for graph snapshots, graph-to-Chunk references, Chunk content, and permissions. Neo4j Provider methods return graph summaries when configured; otherwise graph summary endpoints degrade safely with empty results and diagnostics. P11 consumes Graph API through typed service/adapter layers and never infers authorization locally.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy Core, existing Provider abstraction, React 18, Vite, TypeScript.

---

## File Structure

- Modify: `backend/app/schemas/graph.py` for path/community/diagnostics DTOs and richer supporting Chunk DTO.
- Modify: `backend/app/services/qa_providers.py` for `GraphRetrievalProvider.search_paths()` and `search_communities()` plus local/Neo4j implementations.
- Modify: `backend/app/services/graph_service.py` for path/community search, provider degradation handling, supporting Chunk回表裁剪, and centralized stale helper.
- Modify: `backend/app/api/routes/graph.py` for `/graph/paths` and `/graph/communities`.
- Modify: `backend/app/services/document_service.py` to reuse centralized stale helper after Chunk rewrite and active version switch.
- Create: `backend/scripts/verify_epic9_graph.py` as the local executable verification script for Epic 9 Graph behavior.
- Create: `frontend/src/app/types/graph.ts` for Graph DTO and ViewModel types.
- Create: `frontend/src/app/services/graphService.ts` for Graph API calls.
- Create: `frontend/src/app/adapters/graphAdapter.ts` for DTO-to-P11 ViewModel mapping.
- Modify: `frontend/src/app/pages/P11_GraphSearchAnalysis.tsx` to replace static prototype data with real API state.
- Create: `docs/04-迭代与交付/Epic-9/迭代计划-Sprint-10.md`.
- Modify: `docs/04-迭代与交付/产品待办清单.md` after each backlog is completed.

## Task 1: B-043 Graph Path And Community API

**Files:**
- Modify: `backend/app/schemas/graph.py`
- Modify: `backend/app/services/qa_providers.py`
- Modify: `backend/app/services/graph_service.py`
- Modify: `backend/app/api/routes/graph.py`
- Create: `backend/scripts/verify_epic9_graph.py`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Write the failing verification for paths and communities**

Create `backend/scripts/verify_epic9_graph.py` with this initial content:

```python
"""Verify Epic 9 graph API behavior with FastAPI TestClient.

The script intentionally starts with assertions for endpoints that do not
exist yet, so the first run proves the verification catches missing B-043 work.
"""

from fastapi.testclient import TestClient

from app.main import app


def assert_ok(response, label: str) -> dict:
    """Fail with a compact message that keeps local verification readable."""
    assert response.status_code == 200, f"{label} failed: {response.status_code} {response.text}"
    return response.json()


def main() -> None:
    client = TestClient(app)
    kb_id = "11111111-1111-1111-1111-111111111111"

    paths = assert_ok(client.get(f"/api/v1/knowledge-bases/{kb_id}/graph/paths?keyword=Supplier&limit=5"), "paths")
    assert "items" in paths
    assert "diagnostics" in paths
    assert paths["diagnostics"]["degraded"] in {True, False}

    communities = assert_ok(
        client.get(f"/api/v1/knowledge-bases/{kb_id}/graph/communities?keyword=Supplier&limit=5"),
        "communities",
    )
    assert "items" in communities
    assert "diagnostics" in communities
    assert communities["diagnostics"]["degraded"] in {True, False}


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the verification and confirm RED**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python scripts\verify_epic9_graph.py
```

Expected: FAIL because `/graph/paths` and `/graph/communities` return `404 Not Found`.

- [ ] **Step 3: Add Graph response DTOs**

Update `backend/app/schemas/graph.py` by adding these classes after `GraphEntitySearchResponse`:

```python
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
```

- [ ] **Step 4: Extend Graph Provider methods**

Modify `backend/app/services/qa_providers.py`:

```python
class GraphRetrievalProvider:
    """Graph Retrieval Provider 抽象，图结果必须通过 chunk_id 回落。"""

    # keep existing retrieve() and search_entities()

    def search_paths(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        """Search relationship paths by keyword for P11 diagnostics."""
        raise NotImplementedError

    def search_communities(
        self,
        kb_id: UUID,
        keyword: str | None,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        """Search graph community summaries for P11 diagnostics."""
        raise NotImplementedError
```

Add local implementations:

```python
    def search_paths(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        return []

    def search_communities(
        self,
        kb_id: UUID,
        keyword: str | None,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        return []
```

Add Neo4j implementations:

```python
    def search_paths(
        self,
        kb_id: UUID,
        keyword: str,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        cypher = """
        MATCH (source:Entity)-[rel:RELATED_TO]->(target:Entity)
        WHERE source.kb_id = $kb_id
          AND target.kb_id = $kb_id
          AND ($graph_snapshot_id IS NULL OR source.graph_snapshot_id = $graph_snapshot_id)
          AND ($graph_snapshot_id IS NULL OR target.graph_snapshot_id = $graph_snapshot_id)
          AND (
            toLower(source.name) CONTAINS toLower($keyword)
            OR toLower(target.name) CONTAINS toLower($keyword)
            OR toLower(type(rel)) CONTAINS toLower($keyword)
          )
        RETURN
          coalesce(rel.relation_key, elementId(rel)) AS pathKey,
          source.entity_key AS sourceEntityKey,
          source.name AS sourceName,
          source.type AS sourceType,
          target.entity_key AS targetEntityKey,
          target.name AS targetName,
          target.type AS targetType,
          type(rel) AS relationType,
          coalesce(rel.support_node_key, source.entity_key) AS nodeKey,
          rel.relation_key AS relationKey
        LIMIT $limit
        """
        return self._run_read(cypher, kb_id=kb_id, graph_snapshot_id=graph_snapshot_id, keyword=keyword, limit=limit)

    def search_communities(
        self,
        kb_id: UUID,
        keyword: str | None,
        graph_snapshot_id: UUID | None,
        limit: int,
    ) -> list[dict]:
        cypher = """
        MATCH (community:Community)
        WHERE community.kb_id = $kb_id
          AND ($graph_snapshot_id IS NULL OR community.graph_snapshot_id = $graph_snapshot_id)
          AND (
            $keyword IS NULL
            OR toLower(community.summary) CONTAINS toLower($keyword)
            OR toLower(coalesce(community.title, community.community_key)) CONTAINS toLower($keyword)
          )
        RETURN
          community.community_key AS communityKey,
          coalesce(community.title, community.community_key) AS title,
          community.summary AS summary,
          community.entity_count AS entityCount
        LIMIT $limit
        """
        return self._run_read(cypher, kb_id=kb_id, graph_snapshot_id=graph_snapshot_id, keyword=keyword, limit=limit)
```

- [ ] **Step 5: Add service functions**

In `backend/app/services/graph_service.py`, import the new DTOs and add:

```python
def _degraded_diagnostics(reason: str) -> GraphQueryDiagnosticsDTO:
    """Build a stable degradation payload without leaking provider internals."""
    return GraphQueryDiagnosticsDTO(degraded=True, degradedReason=reason, provider="graph")


def search_graph_paths(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    keyword: str,
    graph_snapshot_id: UUID | None,
    limit: int,
) -> GraphPathSearchResponse | None:
    """Search graph paths and degrade safely when Provider is unavailable."""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    snapshot_id = graph_snapshot_id or _latest_success_snapshot_id(session, kb_id)
    diagnostics = GraphQueryDiagnosticsDTO(provider="graph")
    try:
        rows = get_qa_run_providers().graph.search_paths(kb_id, keyword, snapshot_id, limit)
    except ProviderError:
        rows = []
        diagnostics = _degraded_diagnostics("图 Provider 当前不可用，已返回空路径结果。")
    return GraphPathSearchResponse(
        items=[_to_graph_path_dto(row) for row in rows],
        graphSnapshotId=str(snapshot_id) if snapshot_id else None,
        diagnostics=diagnostics,
    )


def search_graph_communities(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    keyword: str | None,
    graph_snapshot_id: UUID | None,
    limit: int,
) -> GraphCommunitySearchResponse | None:
    """Search graph community summaries and degrade safely."""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None
    snapshot_id = graph_snapshot_id or _latest_success_snapshot_id(session, kb_id)
    diagnostics = GraphQueryDiagnosticsDTO(provider="graph")
    try:
        rows = get_qa_run_providers().graph.search_communities(kb_id, keyword, snapshot_id, limit)
    except ProviderError:
        rows = []
        diagnostics = _degraded_diagnostics("图 Provider 当前不可用，已返回空社区结果。")
    return GraphCommunitySearchResponse(
        items=[_to_graph_community_dto(row) for row in rows],
        graphSnapshotId=str(snapshot_id) if snapshot_id else None,
        diagnostics=diagnostics,
    )
```

Also add compact mapper helpers `_to_graph_path_dto()` and `_to_graph_community_dto()` using the DTO fields from Step 3.

- [ ] **Step 6: Add routes**

In `backend/app/api/routes/graph.py`, import the new responses and service functions, then add:

```python
@router.get("/graph/paths", response_model=GraphPathSearchResponse)
def read_graph_paths(
    kb_id: UUID,
    keyword: Annotated[str, Query(min_length=1)],
    graph_snapshot_id: Annotated[UUID | None, Query(alias="graphSnapshotId")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> GraphPathSearchResponse:
    """Search relationship paths for P11 diagnostics."""
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
    """Search community summaries for P11 diagnostics."""
    response = search_graph_communities(session, current_user, kb_id, keyword, graph_snapshot_id, limit)
    if response is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found.")
    return response
```

- [ ] **Step 7: Run verification and compile**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python scripts\verify_epic9_graph.py
```

Expected: compile passes; verification passes if the default seeded knowledge base ID exists. If the script fails only because local seed data is missing, record that blocker and verify with the actual dev `kbId`.

- [ ] **Step 8: Update backlog and commit B-043**

In `docs/04-迭代与交付/产品待办清单.md`, change `B-043` status from `Todo` to `Done` and owner to `Codex`.

Run:

```powershell
git add backend/app/schemas/graph.py backend/app/services/qa_providers.py backend/app/services/graph_service.py backend/app/api/routes/graph.py backend/scripts/verify_epic9_graph.py docs/04-迭代与交付/产品待办清单.md
git commit -m "feat: complete E9 graph summary APIs"
```

## Task 2: B-044 Supporting Chunk Authorization And filteredCount

**Files:**
- Modify: `backend/app/schemas/graph.py`
- Modify: `backend/app/services/graph_service.py`
- Modify: `backend/scripts/verify_epic9_graph.py`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Add failing verification for supporting Chunk shape**

Extend `backend/scripts/verify_epic9_graph.py`:

```python
    supporting = assert_ok(
        client.get(
            f"/api/v1/knowledge-bases/{kb_id}/graph/supporting-chunks"
            "?graphSnapshotId=22222222-2222-2222-2222-222222222222&nodeKey=missing-node"
        ),
        "supporting chunks",
    )
    assert "items" in supporting
    assert "filteredCount" in supporting
    for item in supporting["items"]:
        assert "chunkId" in item
        assert "contentPreview" in item
        assert "documentName" in item
```

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python scripts\verify_epic9_graph.py
```

Expected: FAIL because `GraphSupportingChunkDTO` does not yet include `contentPreview` and document fields.

- [ ] **Step 2: Extend GraphSupportingChunkDTO**

Replace the existing `GraphSupportingChunkDTO` in `backend/app/schemas/graph.py` with:

```python
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
```

- [ ] **Step 3: Implement Chunk回表裁剪**

In `backend/app/services/graph_service.py`, import `chunks`, `documents`, and `has_kb_permission`. Replace `list_supporting_chunks()` with logic equivalent to:

```python
def _preview(content: str, limit: int = 180) -> str:
    """Return a compact content preview without changing stored Chunk text."""
    stripped = " ".join(content.split())
    return stripped if len(stripped) <= limit else f"{stripped[:limit]}..."


def list_supporting_chunks(
    session: Session,
    current_user: CurrentUserResponse,
    kb_id: UUID,
    graph_snapshot_id: UUID,
    node_key: str | None,
    relation_key: str | None,
    community_key: str | None,
) -> GraphSupportingChunksResponse | None:
    """Return authorized supporting Chunks and count filtered graph references."""
    if _read_visible_knowledge_base(session, current_user, kb_id) is None:
        return None

    condition = graph_chunk_refs.c.graph_snapshot_id == graph_snapshot_id
    if node_key:
        condition = condition & (graph_chunk_refs.c.neo4j_node_key == node_key)
    if relation_key:
        condition = condition & (graph_chunk_refs.c.neo4j_relation_key == relation_key)
    if community_key:
        condition = condition & (graph_chunk_refs.c.community_key == community_key)

    ref_rows = list(session.execute(select(graph_chunk_refs).where(condition).limit(100)).mappings())
    if not ref_rows:
        return GraphSupportingChunksResponse(items=[], filteredCount=0)

    can_read_chunks = has_kb_permission(session, current_user, kb_id, "kb.chunk.read")
    if not can_read_chunks:
        return GraphSupportingChunksResponse(items=[], filteredCount=len(ref_rows))

    refs_by_chunk_id = {row["chunk_id"]: row for row in ref_rows}
    rows = list(
        session.execute(
            select(
                chunks.c.chunk_id,
                chunks.c.document_id,
                chunks.c.chunk_index,
                chunks.c.content,
                chunks.c.security_level,
                documents.c.name.label("document_name"),
            )
            .join(documents, documents.c.document_id == chunks.c.document_id)
            .where(
                chunks.c.chunk_id.in_(refs_by_chunk_id.keys()),
                chunks.c.kb_id == kb_id,
                chunks.c.status == "active",
                documents.c.deleted_at.is_(None),
            )
            .order_by(chunks.c.chunk_index.asc())
        ).mappings()
    )

    returned_chunk_ids = {row["chunk_id"] for row in rows}
    filtered_count = len(ref_rows) - len(returned_chunk_ids)
    return GraphSupportingChunksResponse(
        items=[
            GraphSupportingChunkDTO(
                chunkId=str(row["chunk_id"]),
                documentId=str(row["document_id"]),
                documentName=row["document_name"],
                chunkIndex=row["chunk_index"],
                contentPreview=_preview(row["content"]),
                securityLevel=row["security_level"],
                refType=refs_by_chunk_id[row["chunk_id"]]["ref_type"],
                metadata=refs_by_chunk_id[row["chunk_id"]]["metadata"],
            )
            for row in rows
        ],
        filteredCount=max(filtered_count, 0),
    )
```

- [ ] **Step 4: Run verification and compile**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python scripts\verify_epic9_graph.py
```

Expected: compile passes; supporting chunks response always has `items` and `filteredCount`, and returned items have Chunk preview fields.

- [ ] **Step 5: Update backlog and commit B-044**

In `docs/04-迭代与交付/产品待办清单.md`, change `B-044` status from `Todo` to `Done` and owner to `Codex`.

Run:

```powershell
git add backend/app/schemas/graph.py backend/app/services/graph_service.py backend/scripts/verify_epic9_graph.py docs/04-迭代与交付/产品待办清单.md
git commit -m "feat: add E9 graph supporting chunk filtering"
```

## Task 3: B-046 Stale Marking Rules And Sprint Documentation

**Files:**
- Modify: `backend/app/services/graph_service.py`
- Modify: `backend/app/services/document_service.py`
- Create: `docs/04-迭代与交付/Epic-9/迭代计划-Sprint-10.md`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Add failing stale verification**

Extend `backend/scripts/verify_epic9_graph.py` with a direct import assertion:

```python
from app.services.graph_service import mark_graph_snapshots_stale


def verify_stale_helper_exists() -> None:
    """Ensure B-046 has one shared stale helper instead of scattered updates."""
    assert callable(mark_graph_snapshots_stale)
```

Call `verify_stale_helper_exists()` in `main()`.

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python scripts\verify_epic9_graph.py
```

Expected: FAIL because `mark_graph_snapshots_stale` is not defined yet.

- [ ] **Step 2: Add centralized stale helper**

In `backend/app/services/graph_service.py`, import `update` and add:

```python
def mark_graph_snapshots_stale(
    session: Session,
    kb_id: UUID,
    reason: str,
    current_user: CurrentUserResponse,
) -> None:
    """Mark current successful graph snapshots stale after business truth changes."""
    session.execute(
        update(graph_snapshots)
        .where(graph_snapshots.c.kb_id == kb_id, graph_snapshots.c.status == "success")
        .values(
            status="stale",
            stale_reason=reason,
            stale_at=func.now(),
            updated_at=func.now(),
            updated_by=UUID(current_user.user.userId),
        )
    )
```

- [ ] **Step 3: Reuse helper in document lifecycle**

In `backend/app/services/document_service.py`, import:

```python
from app.services.graph_service import mark_graph_snapshots_stale
```

After deleting/replacing chunks in `_run_local_ingest_worker`, call:

```python
        mark_graph_snapshots_stale(session, kb_row["kb_id"], "chunk_changed", current_user)
```

In `activate_document_version`, replace the direct `update(graph_snapshots)` block with:

```python
    mark_graph_snapshots_stale(session, kb_id, "active_version_changed", current_user)
```

- [ ] **Step 4: Document ACL change handling**

In `docs/04-迭代与交付/Epic-9/迭代计划-Sprint-10.md`, create:

```markdown
# 迭代计划 - Sprint 10

## 1. Sprint 基本信息

- Sprint 名称：Sprint 10
- Sprint 主题：E9 图检索分析与诊断
- 目标：完成图快照、实体路径、社区摘要、支撑 Chunk 回落、权限裁剪和 stale 诊断闭环。

## 2. 关键假设

- PostgreSQL 是 Chunk、权限和图快照元数据真值中心。
- Neo4j 未配置时，图摘要接口返回空结果和降级诊断，不伪造复杂图数据。
- P11 不自行推断权限，所有支撑证据以后端裁剪结果为准。

## 3. 计划事项

| 编号 | Backlog | 标题 | 优先级 | 预估 | 负责人 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| S10-001 | B-043 | 实现图快照、实体搜索、关系路径和社区摘要接口 | P1 | 1d | Codex | Done |
| S10-002 | B-044 | 实现图支撑 Chunk 回落、权限裁剪和 filteredCount 诊断 | P0 | 1d | Codex | Done |
| S10-003 | B-045 | 接入 P11 图检索分析页真实接口 | P1 | 1d | Codex | Todo |
| S10-004 | B-046 | 完善 GraphSnapshot stale 标记规则与文档 | P1 | 0.5d | Codex | Done |

## 4. stale 规则

- 文档 active version 切换后，当前知识库 `success` 图快照标记为 `stale`，原因 `active_version_changed`。
- Chunk 重写或删除后，当前知识库 `success` 图快照标记为 `stale`，原因 `chunk_changed`。
- ACL 或 Chunk 访问过滤摘要变化会影响图支撑 Chunk 可见性，后续权限写接口应复用 `mark_graph_snapshots_stale(..., "acl_changed", ...)`。

## 5. 验收标准

- 图路径和社区接口可返回空结果与降级诊断。
- 支撑 Chunk 查询只返回授权 Chunk，并提供 `filteredCount`。
- P11 可展示快照、图摘要、支撑 Chunk、stale 和权限裁剪提示。
- 后端编译检查和 Epic 9 验证脚本通过，前端构建通过。
```

- [ ] **Step 5: Run verification and compile**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python scripts\verify_epic9_graph.py
```

Expected: compile passes; verification can import the stale helper.

- [ ] **Step 6: Update backlog and commit B-046**

In `docs/04-迭代与交付/产品待办清单.md`, change `B-046` status from `Todo` to `Done` and owner to `Codex`.

Run:

```powershell
git add backend/app/services/graph_service.py backend/app/services/document_service.py backend/scripts/verify_epic9_graph.py docs/04-迭代与交付/Epic-9/迭代计划-Sprint-10.md docs/04-迭代与交付/产品待办清单.md
git commit -m "feat: document E9 graph stale diagnostics"
```

## Task 4: B-045 P11 Real API Integration

**Files:**
- Create: `frontend/src/app/types/graph.ts`
- Create: `frontend/src/app/services/graphService.ts`
- Create: `frontend/src/app/adapters/graphAdapter.ts`
- Modify: `frontend/src/app/pages/P11_GraphSearchAnalysis.tsx`
- Modify: `docs/04-迭代与交付/Epic-9/迭代计划-Sprint-10.md`
- Modify: `docs/04-迭代与交付/产品待办清单.md`

- [ ] **Step 1: Add Graph types**

Create `frontend/src/app/types/graph.ts`:

```typescript
export interface GraphQueryDiagnosticsDTO {
  degraded: boolean;
  degradedReason?: string | null;
  provider: string;
}

export interface GraphSnapshotDTO {
  graphSnapshotId: string;
  kbId: string;
  status: string;
  sourceScope: Record<string, unknown>;
  neo4jGraphKey?: string | null;
  staleReason?: string | null;
  staleAt?: string | null;
  entityCount?: number | null;
  relationCount?: number | null;
  communityCount?: number | null;
  jobId?: string | null;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GraphEntityDTO {
  entityKey?: string | null;
  name: string;
  type?: string | null;
  aliases?: string[] | null;
  metadata: Record<string, unknown>;
}

export interface GraphPathDTO {
  pathKey: string;
  sourceEntity: GraphEntityDTO;
  targetEntity: GraphEntityDTO;
  relationType: string;
  hopCount: number;
  supportKeys: Record<string, string | null>;
  metadata: Record<string, unknown>;
}

export interface GraphCommunityDTO {
  communityKey: string;
  title: string;
  summary: string;
  entityCount?: number | null;
  supportKeys: Record<string, string | null>;
  metadata: Record<string, unknown>;
}

export interface GraphSupportingChunkDTO {
  chunkId: string;
  documentId: string;
  documentName: string;
  chunkIndex: number;
  contentPreview: string;
  securityLevel: string;
  refType: string;
  metadata: Record<string, unknown>;
}

export interface GraphPage<T> {
  items: T[];
  pageNo: number;
  pageSize: number;
  total: number;
}

export interface GraphSearchResponse<T> {
  items: T[];
  graphSnapshotId?: string | null;
  diagnostics: GraphQueryDiagnosticsDTO;
}

export interface GraphSupportingChunksResponse {
  items: GraphSupportingChunkDTO[];
  filteredCount: number;
}
```

- [ ] **Step 2: Add Graph service**

Create `frontend/src/app/services/graphService.ts`:

```typescript
import { apiGet } from "./apiClient";
import type {
  GraphCommunityDTO,
  GraphEntityDTO,
  GraphPage,
  GraphPathDTO,
  GraphSearchResponse,
  GraphSnapshotDTO,
  GraphSupportingChunksResponse,
} from "../types/graph";

function withParams(path: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export async function fetchGraphSnapshots(kbId: string): Promise<GraphPage<GraphSnapshotDTO>> {
  return apiGet<GraphPage<GraphSnapshotDTO>>(`/knowledge-bases/${kbId}/graph-snapshots?pageNo=1&pageSize=20`);
}

export async function searchGraphEntities(
  kbId: string,
  keyword: string,
  graphSnapshotId?: string,
): Promise<GraphSearchResponse<GraphEntityDTO>> {
  const params = new URLSearchParams({ keyword, limit: "20" });
  if (graphSnapshotId) params.set("graphSnapshotId", graphSnapshotId);
  return apiGet<GraphSearchResponse<GraphEntityDTO>>(withParams(`/knowledge-bases/${kbId}/graph/entities`, params));
}

export async function searchGraphPaths(
  kbId: string,
  keyword: string,
  graphSnapshotId?: string,
): Promise<GraphSearchResponse<GraphPathDTO>> {
  const params = new URLSearchParams({ keyword, limit: "20" });
  if (graphSnapshotId) params.set("graphSnapshotId", graphSnapshotId);
  return apiGet<GraphSearchResponse<GraphPathDTO>>(withParams(`/knowledge-bases/${kbId}/graph/paths`, params));
}

export async function searchGraphCommunities(
  kbId: string,
  keyword: string,
  graphSnapshotId?: string,
): Promise<GraphSearchResponse<GraphCommunityDTO>> {
  const params = new URLSearchParams({ limit: "20" });
  if (keyword.trim()) params.set("keyword", keyword.trim());
  if (graphSnapshotId) params.set("graphSnapshotId", graphSnapshotId);
  return apiGet<GraphSearchResponse<GraphCommunityDTO>>(withParams(`/knowledge-bases/${kbId}/graph/communities`, params));
}

export async function fetchGraphSupportingChunks(
  kbId: string,
  graphSnapshotId: string,
  params: { nodeKey?: string | null; relationKey?: string | null; communityKey?: string | null },
): Promise<GraphSupportingChunksResponse> {
  const query = new URLSearchParams({ graphSnapshotId });
  if (params.nodeKey) query.set("nodeKey", params.nodeKey);
  if (params.relationKey) query.set("relationKey", params.relationKey);
  if (params.communityKey) query.set("communityKey", params.communityKey);
  return apiGet<GraphSupportingChunksResponse>(withParams(`/knowledge-bases/${kbId}/graph/supporting-chunks`, query));
}
```

- [ ] **Step 3: Add Graph adapter**

Create `frontend/src/app/adapters/graphAdapter.ts`:

```typescript
import { formatDateTime } from "./documentAdapter";
import type { GraphCommunityDTO, GraphPathDTO, GraphSnapshotDTO, GraphSupportingChunkDTO } from "../types/graph";

export interface GraphSnapshotViewModel {
  id: string;
  status: string;
  statusLabel: string;
  staleReason?: string | null;
  updatedAt: string;
  entityCount: string;
  relationCount: string;
  communityCount: string;
}

export function toGraphSnapshotViewModel(snapshot: GraphSnapshotDTO): GraphSnapshotViewModel {
  return {
    id: snapshot.graphSnapshotId,
    status: snapshot.status,
    statusLabel: snapshot.status === "stale" ? "已过期" : snapshot.status === "success" ? "可用" : snapshot.status,
    staleReason: snapshot.staleReason,
    updatedAt: formatDateTime(snapshot.updatedAt),
    entityCount: String(snapshot.entityCount ?? 0),
    relationCount: String(snapshot.relationCount ?? 0),
    communityCount: String(snapshot.communityCount ?? 0),
  };
}

export function describePath(path: GraphPathDTO): string {
  return `${path.sourceEntity.name} -> ${path.relationType} -> ${path.targetEntity.name}`;
}

export function describeCommunity(community: GraphCommunityDTO): string {
  return `${community.title} · ${community.entityCount ?? 0} entities`;
}

export function describeChunk(chunk: GraphSupportingChunkDTO): string {
  return `${chunk.documentName} #${chunk.chunkIndex} · ${chunk.securityLevel}`;
}
```

- [ ] **Step 4: Replace P11 static prototype with real state**

Modify `frontend/src/app/pages/P11_GraphSearchAnalysis.tsx` to:

```typescript
import { useEffect, useState } from "react";
import { useParams } from "react-router";
import { AlertTriangle, Info, Network, Search, ZoomIn } from "lucide-react";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
import { Input } from "../components/rag/Input";
import { Alert } from "../components/rag/Alert";
import {
  fetchGraphSnapshots,
  fetchGraphSupportingChunks,
  searchGraphCommunities,
  searchGraphEntities,
  searchGraphPaths,
} from "../services/graphService";
import { describeChunk, describeCommunity, describePath, toGraphSnapshotViewModel } from "../adapters/graphAdapter";
import type { GraphCommunityDTO, GraphEntityDTO, GraphPathDTO, GraphSupportingChunkDTO, GraphSnapshotDTO } from "../types/graph";
```

Inside the component, use state for `snapshots`, `selectedSnapshotId`, `keyword`, `entities`, `paths`, `communities`, `supportingChunks`, `filteredCount`, `degradedReason`, `loading`, and `errorMessage`.

Implementation constraints:

- `useEffect` loads snapshots once when `kbId` changes.
- Search button calls entities, paths, and communities in parallel with `Promise.all`.
- Clicking an entity calls supporting chunks with `{ nodeKey: entity.entityKey }`.
- Clicking a path calls supporting chunks with `{ relationKey: path.supportKeys.relationKey }`.
- Clicking a community calls supporting chunks with `{ communityKey: community.communityKey }`.
- If selected snapshot status is `stale`, render an `Alert` with stale reason.
- If `filteredCount > 0`, render an `Alert` warning that some support chunks were filtered by permission.
- If `degradedReason` exists, render an info `Alert`.

Keep the existing visual language: parchment background, warm borders, compact cards, serif headings.

- [ ] **Step 5: Build frontend and fix compile errors**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

Expected: PASS. Fix TypeScript or import errors without changing unrelated pages.

- [ ] **Step 6: Browser check P11**

If dev servers are available, open:

```text
http://localhost:5173/kb/11111111-1111-1111-1111-111111111111/graph
```

Check:

- Snapshot status area renders.
- Empty/degraded graph result state renders without crashing.
- Search action does not mutate unrelated pages.
- Supporting Chunk section shows empty state or authorized chunks.
- Stale and permission filtered messages are visible when API returns those fields.

- [ ] **Step 7: Update backlog, Sprint plan, and commit B-045**

In `docs/04-迭代与交付/产品待办清单.md`, change `B-045` status from `Todo` to `Done` and owner to `Codex`.

In `docs/04-迭代与交付/Epic-9/迭代计划-Sprint-10.md`, change `S10-003` status from `Todo` to `Done`.

Run:

```powershell
git add frontend/src/app/types/graph.ts frontend/src/app/services/graphService.ts frontend/src/app/adapters/graphAdapter.ts frontend/src/app/pages/P11_GraphSearchAnalysis.tsx docs/04-迭代与交付/Epic-9/迭代计划-Sprint-10.md docs/04-迭代与交付/产品待办清单.md
git commit -m "feat: connect E9 graph analysis page"
```

## Task 5: Final Verification And Review Prep

**Files:**
- Modify only files that need small fixes from verification.

- [ ] **Step 1: Run backend verification**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab python scripts\verify_epic9_graph.py
```

Expected: compile passes; Epic 9 verification passes or reports only documented missing local seed data.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

Expected: PASS.

- [ ] **Step 3: Check backlog statuses**

Run:

```powershell
rg -n "B-043|B-044|B-045|B-046|S10-" docs\04-迭代与交付
```

Expected: `B-043` to `B-046` are `Done | Codex`; `S10-001` to `S10-004` are `Done`.

- [ ] **Step 4: Inspect git history**

Run:

```powershell
git log --oneline -n 6
git status --short
```

Expected: separate commits exist for B-043, B-044, B-046, B-045; no unrelated files are staged.

- [ ] **Step 5: Request code review**

After all verification passes, use `superpowers:requesting-code-review` before claiming Epic 9 is complete.
