"""Run a database-backed App Runtime smoke regression.

This script creates an isolated KB/RAG App/API key fixture, replaces QA
providers with deterministic local fakes, and verifies the external
blocking chat API plus security boundaries.
"""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
import sys
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy import insert, update

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import app_runtime_service, qa_run_service  # noqa: E402
from app.services.qa_providers import (  # noqa: E402
    IdentityRerankProvider,
    LocalEmbeddingProvider,
    LocalGraphRetrievalProvider,
    LocalLlmProvider,
    LocalSparseRetrievalProvider,
    ProviderCandidate,
    QARunProviders,
)
from app.tables import (  # noqa: E402
    app_invocations,
    chunk_access_filters,
    chunks,
    document_versions,
    documents,
    knowledge_bases,
    rag_app_api_keys,
    stored_files,
)


ADMIN_HEADERS = {"X-Dev-User": "admin"}


class SeededDenseProvider:
    """返回一个授权 Chunk 和一个治理排除 Chunk，验证 Citation 安全边界。"""

    def __init__(self, allowed_chunk_id: UUID, excluded_chunk_id: UUID) -> None:
        self.allowed_chunk_id = allowed_chunk_id
        self.excluded_chunk_id = excluded_chunk_id

    def upsert_chunks(self, chunk_payloads: list[dict]) -> dict:
        """Smoke 脚本不执行索引写入，仅保持 Provider 接口完整。"""
        return {"provider": "seeded", "operation": "upsert", "chunkCount": len(chunk_payloads)}

    def delete_chunks(self, chunk_ids: list[UUID]) -> dict:
        """Smoke 脚本不执行索引删除，仅保持 Provider 接口完整。"""
        return {"provider": "seeded", "operation": "delete", "chunkCount": len(chunk_ids)}

    def retrieve(self, kb_id: UUID, query: str, embedding: list[float], limit: int, access_filter) -> list[ProviderCandidate]:
        """返回固定候选；正文最终必须回 PostgreSQL 真值表确认。"""
        return [
            ProviderCandidate(
                source_type="dense",
                chunk_id=self.allowed_chunk_id,
                raw_score=0.96,
                content="provider stale allowed",
                metadata={"provider": "seeded", "kbId": str(kb_id)},
            ),
            ProviderCandidate(
                source_type="dense",
                chunk_id=self.excluded_chunk_id,
                raw_score=0.95,
                content="provider stale excluded",
                metadata={"provider": "seeded", "kbId": str(kb_id)},
            ),
        ][:limit]


def _assert_status(response, expected_status: int, label: str) -> None:
    """让 smoke 失败信息带上具体阶段，便于定位。"""
    if response.status_code != expected_status:
        raise AssertionError(f"{label}: expected {expected_status}, got {response.status_code}: {response.text}")


def _read_invocation_error_count(app_id: str, error_code: str) -> int:
    """从审计表读取指定错误数量，确认拒绝调用也可追踪。"""
    session = get_session_factory()()
    try:
        return session.execute(
            sa.select(sa.func.count())
            .select_from(app_invocations)
            .where(
                app_invocations.c.app_id == UUID(app_id),
                app_invocations.c.status == "failed",
                app_invocations.c.error_code == error_code,
            )
        ).scalar_one()
    finally:
        session.close()


def _read_invocation_count_by_status(app_id: str, status: str) -> int:
    """按状态读取调用记录数量，验证 running 记录的生命周期。"""
    session = get_session_factory()()
    try:
        return session.execute(
            sa.select(sa.func.count())
            .select_from(app_invocations)
            .where(
                app_invocations.c.app_id == UUID(app_id),
                app_invocations.c.status == status,
            )
        ).scalar_one()
    finally:
        session.close()


def _read_api_key_row_count(api_key: str) -> int:
    """按明文 Key 的 hash 确认物理删除后不再保留 Key 行。"""
    session = get_session_factory()()
    try:
        return session.execute(
            sa.select(sa.func.count())
            .select_from(rag_app_api_keys)
            .where(rag_app_api_keys.c.key_hash == sha256(api_key.encode("utf-8")).hexdigest())
        ).scalar_one()
    finally:
        session.close()


def _read_invocation_count_for_api_key(api_key_id: str) -> int:
    """确认删除 Key 时会解除调用审计中的 Key 外键引用。"""
    session = get_session_factory()()
    try:
        return session.execute(
            sa.select(sa.func.count())
            .select_from(app_invocations)
            .where(app_invocations.c.api_key_id == UUID(api_key_id))
        ).scalar_one()
    finally:
        session.close()


def _assert_runtime_invocation_is_running(app_id: str) -> None:
    """在 QARun 创建前确认 Runtime 已写入 running invocation。"""
    running_count = _read_invocation_count_by_status(app_id, "running")
    if running_count < 1:
        raise AssertionError("running invocation was not visible before QARun execution")


def _seed_chunks(kb_id: UUID) -> tuple[UUID, UUID]:
    """写入一个可引用 Chunk 和一个治理排除 Chunk。"""
    now = datetime.now(UTC)
    document_id = uuid4()
    version_id = uuid4()
    file_id = uuid4()
    allowed_chunk_id = uuid4()
    excluded_chunk_id = uuid4()
    session = get_session_factory()()
    try:
        session.execute(
            insert(stored_files).values(
                file_id=file_id,
                bucket="smoke",
                object_key=f"app-runtime/{file_id}.txt",
                file_name="app-runtime-smoke.txt",
                mime_type="text/plain",
                file_size=128,
                checksum=None,
                file_role="source",
                status="active",
                created_at=now,
                created_by=UUID("00000000-0000-0000-0000-000000000001"),
            )
        )
        session.execute(
            insert(documents).values(
                document_id=document_id,
                kb_id=kb_id,
                name="app-runtime-smoke.txt",
                source_type="upload",
                status="active",
                active_version_id=None,
                metadata={"smoke": "app-runtime"},
                created_at=now,
                created_by=UUID("00000000-0000-0000-0000-000000000001"),
                updated_at=now,
                updated_by=UUID("00000000-0000-0000-0000-000000000001"),
            )
        )
        session.execute(
            insert(document_versions).values(
                version_id=version_id,
                document_id=document_id,
                version_no=1,
                source_file_id=file_id,
                status="active",
                parse_status="success",
                dense_index_status="success",
                sparse_index_status="not_required",
                graph_index_status="not_required",
                retrieval_ready=True,
                chunk_count=2,
                token_count=32,
                error_code=None,
                error_message=None,
                metadata={"smoke": "app-runtime"},
                created_at=now,
                created_by=UUID("00000000-0000-0000-0000-000000000001"),
                updated_at=now,
                updated_by=UUID("00000000-0000-0000-0000-000000000001"),
            )
        )
        session.execute(
            update(documents)
            .where(documents.c.document_id == document_id)
            .values(active_version_id=version_id)
        )
        for chunk_id, index, content, metadata in [
            (allowed_chunk_id, 1, "App Runtime smoke allowed evidence.", {"smoke": "allowed"}),
            (excluded_chunk_id, 2, "App Runtime smoke excluded evidence.", {"governance": {"excluded": True}}),
        ]:
            session.execute(
                insert(chunks).values(
                    chunk_id=chunk_id,
                    version_id=version_id,
                    document_id=document_id,
                    kb_id=kb_id,
                    chunk_index=index,
                    page_no=1,
                    section=f"Smoke {index}",
                    content=content,
                    content_hash=sha256(content.encode("utf-8")).hexdigest(),
                    token_count=8,
                    status="active",
                    metadata=metadata,
                    created_at=now,
                )
            )
            session.execute(
                insert(chunk_access_filters).values(
                    access_filter_id=uuid4(),
                    chunk_id=chunk_id,
                    kb_id=kb_id,
                    permission_code="kb.chunk.read",
                    allow_subject_keys=[],
                    deny_subject_keys=[],
                    document_status="active",
                    version_status="active",
                    chunk_status="active",
                    filter_hash=None,
                    updated_at=now,
                )
            )
        session.commit()
    finally:
        session.close()
    return allowed_chunk_id, excluded_chunk_id


def _install_seeded_providers(allowed_chunk_id: UUID, excluded_chunk_id: UUID) -> None:
    """替换 QARun Provider，避免 smoke 依赖外部模型或检索服务。"""
    qa_run_service.get_qa_run_providers = lambda: QARunProviders(
        embedding=LocalEmbeddingProvider(),
        dense=SeededDenseProvider(allowed_chunk_id, excluded_chunk_id),
        sparse=LocalSparseRetrievalProvider(),
        graph=LocalGraphRetrievalProvider(),
        rerank=IdentityRerankProvider(),
        llm=LocalLlmProvider(),
    )


def main() -> None:
    """执行 App Runtime blocking API 端到端 smoke 回归。"""
    client = TestClient(create_app())
    suffix = uuid4().hex[:8]

    kb_response = client.post(
        "/api/v1/knowledge-bases",
        headers=ADMIN_HEADERS,
        json={"name": f"app-runtime-smoke-{suffix}", "description": "App Runtime smoke fixture"},
    )
    _assert_status(kb_response, 201, "create knowledge base")
    kb = kb_response.json()
    kb_id = UUID(kb["kbId"])
    active_revision_id = kb["activeConfigRevisionId"]
    allowed_chunk_id, excluded_chunk_id = _seed_chunks(kb_id)
    _install_seeded_providers(allowed_chunk_id, excluded_chunk_id)

    app_response = client.post(
        "/api/v1/rag-apps",
        headers=ADMIN_HEADERS,
        json={"kbId": str(kb_id), "name": f"runtime-smoke-{suffix}"},
    )
    _assert_status(app_response, 201, "create rag app")
    app_id = app_response.json()["appId"]

    key_response = client.post(f"/api/v1/rag-apps/{app_id}/api-keys", headers=ADMIN_HEADERS, json={"name": "smoke"})
    _assert_status(key_response, 201, "create app api key")
    api_key = key_response.json()["apiKey"]

    invalid_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": "Bearer invalid"},
        json={"query": "hello"},
    )
    _assert_status(invalid_response, 401, "invalid key")

    original_create_qa_run = app_runtime_service.create_qa_run

    def create_qa_run_with_running_assertion(*args, **kwargs):
        """确认 Runtime 调用开始即创建 running 审计记录，再执行真实 QARun。"""
        _assert_runtime_invocation_is_running(app_id)
        return original_create_qa_run(*args, **kwargs)

    app_runtime_service.create_qa_run = create_qa_run_with_running_assertion
    try:
        valid_response = client.post(
            "/api/v1/app-runtime/chat-messages",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": "What is the smoke evidence?", "endUserId": f"smoke-{suffix}"},
        )
    finally:
        app_runtime_service.create_qa_run = original_create_qa_run
    _assert_status(valid_response, 200, "valid chat")
    if _read_invocation_count_by_status(app_id, "running") != 0:
        raise AssertionError("running invocation was not finalized after successful chat")
    if _read_invocation_count_by_status(app_id, "success") < 1:
        raise AssertionError("successful chat did not finalize invocation as success")
    payload = valid_response.json()
    required_fields = {"answer", "citations", "conversationId", "messageId", "runId", "usage"}
    missing_fields = required_fields - set(payload)
    if missing_fields:
        raise AssertionError(f"valid chat missing fields: {sorted(missing_fields)}")
    cited_chunk_ids = {item["locationSnapshot"].get("chunkId") for item in payload["citations"]}
    if str(allowed_chunk_id) not in cited_chunk_ids:
        raise AssertionError("allowed chunk was not cited")
    if str(excluded_chunk_id) in cited_chunk_ids:
        raise AssertionError("governance excluded chunk leaked into citations")

    streaming_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"query": "Stream the smoke evidence.", "responseMode": "streaming"},
    )
    _assert_status(streaming_response, 200, "streaming chat")
    if "text/event-stream" not in streaming_response.headers.get("content-type", ""):
        raise AssertionError(f"streaming content-type mismatch: {streaming_response.headers}")
    stream_text = streaming_response.text
    for expected_event in ["event: answer_delta", "event: citation", "event: usage", "event: done"]:
        if expected_event not in stream_text:
            raise AssertionError(f"streaming response missing {expected_event}: {stream_text}")

    feedback_response = client.post(
        f"/api/v1/app-runtime/messages/{payload['messageId']}/feedback",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "feedbackStatus": "wrong",
            "feedbackNote": "Smoke feedback should flow back to QARun.",
            "failureType": "answer_mismatch",
            "createEvaluationSample": True,
        },
    )
    _assert_status(feedback_response, 201, "runtime feedback")
    feedback_payload = feedback_response.json()
    if feedback_payload.get("feedbackStatus") != "wrong" or not feedback_payload.get("evaluationSampleId"):
        raise AssertionError(f"runtime feedback payload mismatch: {feedback_response.text}")

    stats_response = client.get(f"/api/v1/rag-apps/{app_id}/stats", headers=ADMIN_HEADERS)
    _assert_status(stats_response, 200, "app invocation stats")
    stats_payload = stats_response.json()
    if stats_payload.get("totalInvocations", 0) < 2 or stats_payload.get("successInvocations", 0) < 2:
        raise AssertionError(f"stats did not include successful runtime calls: {stats_response.text}")

    limited_app_response = client.post(
        "/api/v1/rag-apps",
        headers=ADMIN_HEADERS,
        json={
            "kbId": str(kb_id),
            "name": f"runtime-smoke-limited-{suffix}",
            "metadata": {"runtimeLimits": {"minuteLimit": 1, "dailyQuota": 10}},
        },
    )
    _assert_status(limited_app_response, 201, "create limited rag app")
    limited_app_id = limited_app_response.json()["appId"]
    limited_key_response = client.post(
        f"/api/v1/rag-apps/{limited_app_id}/api-keys",
        headers=ADMIN_HEADERS,
        json={"name": "smoke-limited"},
    )
    _assert_status(limited_key_response, 201, "create limited key")
    limited_key = limited_key_response.json()["apiKey"]
    first_limited_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {limited_key}"},
        json={"query": "first limited call"},
    )
    _assert_status(first_limited_response, 200, "first limited call")
    second_limited_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {limited_key}"},
        json={"query": "second limited call"},
    )
    _assert_status(second_limited_response, 429, "rate limited call")
    if second_limited_response.json().get("detail") != "RAG_APP_QUOTA_EXCEEDED":
        raise AssertionError(f"rate limit detail mismatch: {second_limited_response.text}")
    if _read_invocation_error_count(limited_app_id, "RAG_APP_QUOTA_EXCEEDED") < 1:
        raise AssertionError("rate limited invocation was not written to audit table")

    concurrent_app_response = client.post(
        "/api/v1/rag-apps",
        headers=ADMIN_HEADERS,
        json={
            "kbId": str(kb_id),
            "name": f"runtime-smoke-concurrent-{suffix}",
            "metadata": {"runtimeLimits": {"maxConcurrent": 1}},
        },
    )
    _assert_status(concurrent_app_response, 201, "create concurrency limited rag app")
    concurrent_app_id = concurrent_app_response.json()["appId"]
    concurrent_key_response = client.post(
        f"/api/v1/rag-apps/{concurrent_app_id}/api-keys",
        headers=ADMIN_HEADERS,
        json={"name": "smoke-concurrent"},
    )
    _assert_status(concurrent_key_response, 201, "create concurrency limited key")
    concurrent_key = concurrent_key_response.json()["apiKey"]
    session = get_session_factory()()
    try:
        session.execute(
            insert(app_invocations).values(
                invocation_id=uuid4(),
                app_id=UUID(concurrent_app_id),
                api_key_id=UUID(concurrent_key_response.json()["item"]["apiKeyId"]),
                status="running",
                error_code=None,
                latency_ms=None,
                request_summary={"fixture": "running-concurrency-slot"},
                response_summary={},
                created_at=datetime.now(UTC),
            )
        )
        session.commit()
    finally:
        session.close()
    concurrent_rejected_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {concurrent_key}"},
        json={"query": "should be rejected by maxConcurrent"},
    )
    _assert_status(concurrent_rejected_response, 429, "concurrency limited call")
    if concurrent_rejected_response.json().get("detail") != "RAG_APP_CONCURRENCY_EXCEEDED":
        raise AssertionError(f"concurrency limit detail mismatch: {concurrent_rejected_response.text}")
    if _read_invocation_error_count(concurrent_app_id, "RAG_APP_CONCURRENCY_EXCEEDED") < 1:
        raise AssertionError("concurrency limited invocation was not written to audit table")
    concurrent_stats_response = client.get(f"/api/v1/rag-apps/{concurrent_app_id}/stats", headers=ADMIN_HEADERS)
    _assert_status(concurrent_stats_response, 200, "concurrency app stats")
    concurrent_stats_payload = concurrent_stats_response.json()
    if concurrent_stats_payload.get("runningInvocations", 0) < 1:
        raise AssertionError(f"stats did not include running invocations: {concurrent_stats_response.text}")
    if concurrent_stats_payload.get("concurrencyExceededInvocations", 0) < 1:
        raise AssertionError(f"stats did not include concurrency rejects: {concurrent_stats_response.text}")

    second_app_response = client.post(
        "/api/v1/rag-apps",
        headers=ADMIN_HEADERS,
        json={"kbId": str(kb_id), "name": f"runtime-smoke-second-{suffix}"},
    )
    _assert_status(second_app_response, 201, "create second rag app")
    second_app_id = second_app_response.json()["appId"]
    second_key_response = client.post(
        f"/api/v1/rag-apps/{second_app_id}/api-keys",
        headers=ADMIN_HEADERS,
        json={"name": "smoke-second"},
    )
    _assert_status(second_key_response, 201, "create second key")
    second_key = second_key_response.json()["apiKey"]
    cross_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {second_key}"},
        json={"query": "cross app?", "conversationId": payload["conversationId"]},
    )
    _assert_status(cross_response, 404, "cross app conversation isolation")

    disabled_response = client.patch(f"/api/v1/rag-apps/{app_id}", headers=ADMIN_HEADERS, json={"status": "disabled"})
    _assert_status(disabled_response, 200, "disable app")
    disabled_chat_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"query": "disabled app?"},
    )
    _assert_status(disabled_chat_response, 409, "disabled app chat")
    if disabled_chat_response.json().get("detail") != "RAG_APP_DISABLED":
        raise AssertionError(f"disabled app detail mismatch: {disabled_chat_response.text}")
    reenabled_response = client.patch(f"/api/v1/rag-apps/{app_id}", headers=ADMIN_HEADERS, json={"status": "active"})
    _assert_status(reenabled_response, 200, "reenable app")

    session = get_session_factory()()
    try:
        session.execute(
            update(knowledge_bases)
            .where(knowledge_bases.c.kb_id == kb_id)
            .values(active_config_revision_id=None)
        )
        session.commit()
    finally:
        session.close()
    no_revision_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"query": "no revision?"},
    )
    _assert_status(no_revision_response, 409, "missing active revision")
    if no_revision_response.json().get("detail") != "RAG_APP_NO_RUNNABLE_REVISION":
        raise AssertionError(f"missing revision detail mismatch: {no_revision_response.text}")

    session = get_session_factory()()
    try:
        session.execute(
            update(knowledge_bases)
            .where(knowledge_bases.c.kb_id == kb_id)
            .values(active_config_revision_id=UUID(active_revision_id))
        )
        session.commit()
    finally:
        session.close()

    api_key_id = key_response.json()["item"]["apiKeyId"]
    delete_key_response = client.delete(f"/api/v1/rag-apps/{app_id}/api-keys/{api_key_id}", headers=ADMIN_HEADERS)
    _assert_status(delete_key_response, 204, "delete key")
    if _read_api_key_row_count(api_key) != 0:
        raise AssertionError("deleted API Key row is still stored")
    if _read_invocation_count_for_api_key(api_key_id) != 0:
        raise AssertionError("deleted API Key is still referenced by invocation audit records")
    deleted_key_response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"query": "deleted key?"},
    )
    _assert_status(deleted_key_response, 401, "deleted key")
    print("app-runtime smoke passed")


if __name__ == "__main__":
    main()
