"""验证内部客服 langgraph_primary_v1 的真实发布级 E2E。

脚本只允许连接显式指定的独立测试库。它复用真实 Provider 文档入库链路，
验证连续追问、Checkpoint 恢复、摘要、Tool 审计、Runtime Trace 和 QARun 串联。
"""
from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import select, text


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


TRACE_FIELDS = (
    "agentInvocationId",
    "threadId",
    "checkpointId",
    "scenarioType",
    "runtimeVersion",
    "qaRunId",
    "skillCallId",
    "modelCallId",
    "summaryVersion",
)


def _database_identity(url: str) -> tuple[str, int | None, str]:
    """提取 DSN 的主机、端口和数据库名，避免比较密码等敏感信息。"""
    normalized = url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )
    parts = urlsplit(normalized)
    return parts.hostname or "", parts.port, parts.path.lstrip("/")


def _validate_test_database_urls(test_database_url: str | None, checkpoint_database_url: str | None) -> None:
    """拒绝隐式业务库和 Checkpoint 跨库，保护真实 E2E 的写入边界。"""
    if not test_database_url:
        raise AssertionError("必须显式设置 RAG_LAB_TEST_POSTGRES_URL。")
    if not checkpoint_database_url:
        raise AssertionError("必须显式设置 RAG_LAB_AGENT_RUNTIME_CHECKPOINT_DATABASE_URL。")

    test_identity = _database_identity(test_database_url)
    checkpoint_identity = _database_identity(checkpoint_database_url)
    if test_identity != checkpoint_identity:
        raise AssertionError("业务数据和 Checkpoint 必须使用同一个独立测试数据库。")
    if not test_identity[2].endswith("_test"):
        raise AssertionError("真实 E2E 数据库名必须以 _test 结尾。")


def _assert_trace_summary(summary: dict) -> None:
    """校验 Runtime 摘要具备 Graph、Tool 和 QARun 全链路关联字段。"""
    for field in TRACE_FIELDS:
        if summary.get(field) in (None, ""):
            raise AssertionError(f"Runtime Trace 缺少 {field}: {summary}")
    if int(summary["summaryVersion"]) < 0:
        raise AssertionError(f"summaryVersion 不能小于 0: {summary}")


def _assert_status(response, expected_status: int, label: str) -> None:
    """在 HTTP 断言失败时保留响应正文，便于发布复核。"""
    if response.status_code != expected_status:
        raise AssertionError(f"{label}: expected {expected_status}, got {response.status_code}: {response.text}")


def _chat(client, api_key: str, query: str, conversation_id: str | None = None) -> dict:
    """调用 App Runtime blocking 对话接口。"""
    payload = {"query": query, "endUserId": "primary-e2e-user"}
    if conversation_id:
        payload["conversationId"] = conversation_id
    response = client.post(
        "/api/v1/app-runtime/chat-messages",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
    )
    _assert_status(response, 200, "app runtime chat")
    return response.json()


def _reset_test_business_schema(engine, metadata) -> None:
    """在已校验的独立测试库中重建业务 Schema，确保每次 E2E 相互隔离。

    历史 PostgreSQL 迁移链不能从空库完整重放，因此发布脚本使用当前表声明建表。
    服务层依赖数据库自动生成时间戳，这里只在测试库补齐对应默认值。
    """
    metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    metadata.create_all(engine)
    with engine.begin() as connection:
        for table in metadata.sorted_tables:
            for column in table.columns:
                if column.name in {"created_at", "updated_at"} and not column.nullable:
                    connection.execute(
                        text(f'ALTER TABLE "{table.name}" ALTER COLUMN "{column.name}" SET DEFAULT now()')
                    )


def _stable_id(value: str) -> str:
    """生成可重复执行的测试种子 UUID。"""
    return str(uuid5(NAMESPACE_URL, f"rag-lab-primary-e2e:{value}"))


def _seed_test_reference_data(engine) -> None:
    """写入真实链路需要的最小权限、用户和系统字典种子。"""
    permission_codes = (
        "kb.view",
        "kb.manage",
        "kb.member.manage",
        "kb.document.upload",
        "kb.document.read",
        "kb.document.download",
        "kb.chunk.read",
        "kb.config.manage",
        "kb.qa.run",
        "kb.qa.history.read",
        "kb.evaluation.manage",
        "kb.app.manage",
        "app.manage",
        "app.key.manage",
    )
    dictionary_items = {
        "document_source_type": ("upload",),
        "file_role": ("source",),
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO users (
                    user_id, username, display_name, email, platform_role,
                    security_level, status
                )
                VALUES (
                    :user_id, 'admin', '开发管理员', 'admin@example.com',
                    'platform_admin', 'internal', 'active'
                )
                """
            ),
            {"user_id": "00000000-0000-0000-0000-000000000001"},
        )
        for permission_code in permission_codes:
            connection.execute(
                text(
                    """
                    INSERT INTO permissions (
                        permission_id, permission_code, scope, name, status
                    )
                    VALUES (:permission_id, :permission_code, 'kb', :permission_code, 'active')
                    """
                ),
                {
                    "permission_id": _stable_id(f"permission:{permission_code}"),
                    "permission_code": permission_code,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO role_permission_bindings (
                        role_permission_id, role_scope, role_code,
                        permission_code, effect, status
                    )
                    VALUES (
                        :binding_id, 'platform', 'platform_admin',
                        :permission_code, 'allow', 'active'
                    )
                    """
                ),
                {
                    "binding_id": _stable_id(f"platform-admin:{permission_code}"),
                    "permission_code": permission_code,
                },
            )

        for type_code, item_codes in dictionary_items.items():
            dict_type_id = _stable_id(f"dict-type:{type_code}")
            connection.execute(
                text(
                    """
                    INSERT INTO system_dict_types (
                        dict_type_id, code, name, status
                    )
                    VALUES (:dict_type_id, :type_code, :type_code, 'active')
                    """
                ),
                {"dict_type_id": dict_type_id, "type_code": type_code},
            )
            for sort_order, item_code in enumerate(item_codes, start=1):
                connection.execute(
                    text(
                        """
                        INSERT INTO system_dict_items (
                            dict_item_id, dict_type_id, code, name,
                            sort_order, status, extra
                        )
                        VALUES (
                            :dict_item_id, :dict_type_id, :item_code, :item_code,
                            :sort_order, 'active', '{}'
                        )
                        """
                    ),
                    {
                        "dict_item_id": _stable_id(f"dict-item:{type_code}:{item_code}"),
                        "dict_type_id": dict_type_id,
                        "item_code": item_code,
                        "sort_order": sort_order,
                    },
                )


def main() -> None:
    """执行真实 Primary E2E，并输出不包含密钥的 JSON 证据。"""
    test_database_url = os.getenv("RAG_LAB_TEST_POSTGRES_URL")
    checkpoint_database_url = os.getenv("RAG_LAB_AGENT_RUNTIME_CHECKPOINT_DATABASE_URL")
    _validate_test_database_urls(test_database_url, checkpoint_database_url)

    # 业务表和 Checkpoint 必须在导入应用前锁定到同一个独立测试库。
    os.environ["RAG_LAB_DATABASE_URL"] = test_database_url
    os.environ["RAG_LAB_AGENT_RUNTIME_CHECKPOINT_BACKEND"] = "postgres"
    os.environ["RAG_LAB_AGENT_RUNTIME_CHECKPOINT_DATABASE_URL"] = checkpoint_database_url
    os.environ["RAG_LAB_AGENT_RUNTIME_ENABLED"] = "true"
    os.environ["RAG_LAB_AGENT_RUNTIME_DEFAULT_VERSION"] = "langgraph_primary_v1"
    os.environ.setdefault("RAG_LAB_AGENT_RUNTIME_SUMMARY_TRIGGER_TOKENS", "512")
    os.environ.setdefault("RAG_LAB_AGENT_RUNTIME_SUMMARY_KEEP_MESSAGES", "2")

    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.core.database import get_engine, get_session_factory
    from app.main import create_app
    from app.services.agent_runtime.checkpoint_service import create_checkpointer
    from app.services.agent_runtime.runtime_facade import _close_shared_checkpointer
    from app.tables import app_invocations, metadata, qa_runs, training_skill_calls
    from scripts.setup_langgraph_checkpoints import _to_psycopg_dsn
    from scripts.verify_app_runtime_real_provider_e2e import (
        ADMIN_HEADERS,
        _ensure_real_provider_settings,
        _read_chunk_content,
        _relax_active_pipeline_for_smoke,
        _upload_and_ingest_document,
    )

    get_settings.cache_clear()
    _ensure_real_provider_settings()
    _reset_test_business_schema(get_engine(), metadata)
    _seed_test_reference_data(get_engine())
    with create_checkpointer(backend="postgres", database_url=_to_psycopg_dsn(checkpoint_database_url)) as checkpointer:
        checkpointer.setup()

    client = TestClient(create_app())
    marker = f"primary-{uuid4().hex[:8]}"
    kb_response = client.post(
        "/api/v1/knowledge-bases",
        headers=ADMIN_HEADERS,
        json={"name": f"agent-runtime-primary-{marker}", "sparseIndexEnabled": False, "graphIndexEnabled": False},
    )
    _assert_status(kb_response, 201, "create knowledge base")
    kb_id = UUID(kb_response.json()["kbId"])
    _relax_active_pipeline_for_smoke(kb_id)
    document_id = _upload_and_ingest_document(kb_id, marker)

    app_response = client.post(
        "/api/v1/rag-apps",
        headers=ADMIN_HEADERS,
        json={"kbId": str(kb_id), "name": f"agent-runtime-primary-{marker}"},
    )
    _assert_status(app_response, 201, "create rag app")
    app_id = app_response.json()["appId"]
    key_response = client.post(f"/api/v1/rag-apps/{app_id}/api-keys", headers=ADMIN_HEADERS, json={})
    _assert_status(key_response, 201, "create app api key")
    api_key = key_response.json()["apiKey"]

    responses = [
        _chat(client, api_key, f"请检索并说明文档中的 marker {marker}。"),
    ]
    conversation_id = responses[0]["conversationId"]
    responses.append(_chat(client, api_key, "连续追问：刚才文档中的 marker 是什么？", conversation_id))

    # 模拟进程级 Checkpointer 重建，再使用同一 conversationId 恢复。
    _close_shared_checkpointer()
    responses.append(_chat(client, api_key, "恢复后继续：请再次给出刚才的 marker。", conversation_id))

    long_context = f"请结合刚才的 marker {marker} 回答，并记住这段上下文。" + ("摘要触发上下文。" * 120)
    for index in range(4):
        responses.append(_chat(client, api_key, f"第 {index + 1} 次长追问：{long_context}", conversation_id))

    session = get_session_factory()()
    try:
        invocation_rows = list(
            session.execute(
                select(app_invocations)
                .where(app_invocations.c.app_id == UUID(app_id))
                .order_by(app_invocations.c.created_at.asc())
            ).mappings()
        )
        if len(invocation_rows) != len(responses):
            raise AssertionError(f"调用审计数量不一致: responses={len(responses)}, invocations={len(invocation_rows)}")

        trace_summaries = [dict(row["response_summary"] or {}) for row in invocation_rows]
        for summary in trace_summaries:
            _assert_trace_summary(summary)
        if int(trace_summaries[-1]["summaryVersion"]) < 1:
            raise AssertionError(f"长对话没有触发官方摘要中间件: {trace_summaries[-1]}")
        if trace_summaries[-1].get("summaryStatus") != "success":
            raise AssertionError(f"官方摘要中间件没有成功完成摘要: {trace_summaries[-1]}")

        qa_run_ids = [str(row["qa_run_id"]) for row in invocation_rows if row["qa_run_id"]]
        persisted_qa_run_ids = set(
            str(value)
            for value in session.execute(select(qa_runs.c.run_id).where(qa_runs.c.run_id.in_(qa_run_ids))).scalars()
        )
        if set(qa_run_ids) != persisted_qa_run_ids:
            raise AssertionError(f"QARun 串联不完整: expected={qa_run_ids}, actual={sorted(persisted_qa_run_ids)}")

        skill_call_ids = [summary["skillCallId"] for summary in trace_summaries]
        persisted_skill_call_ids = set(
            str(value)
            for value in session.execute(
                select(training_skill_calls.c.skill_call_id).where(
                    training_skill_calls.c.skill_call_id.in_(skill_call_ids),
                    training_skill_calls.c.skill_name == "query_knowledge_base",
                )
            ).scalars()
        )
        if set(skill_call_ids) != persisted_skill_call_ids:
            raise AssertionError(
                f"Tool 审计串联不完整: expected={skill_call_ids}, actual={sorted(persisted_skill_call_ids)}"
            )
    finally:
        session.close()
        _close_shared_checkpointer()

    cited_chunk_ids = [
        item.get("locationSnapshot", {}).get("chunkId")
        for response in responses
        for item in response.get("citations") or []
        if item.get("locationSnapshot", {}).get("chunkId")
    ]
    if not cited_chunk_ids:
        raise AssertionError("真实 Primary 响应没有 Citation。")
    if not any(marker in _read_chunk_content(chunk_id) for chunk_id in cited_chunk_ids):
        raise AssertionError(f"没有 Citation 指向包含 marker {marker} 的 PostgreSQL Chunk。")

    latest_metadata = responses[-1]["metadata"]
    result = {
        "status": "success",
        "verifiedAt": datetime.now(UTC).isoformat(),
        "documentId": str(document_id),
        "appId": app_id,
        "conversationId": conversation_id,
        "threadId": latest_metadata.get("threadId"),
        "checkpointId": latest_metadata.get("checkpointId"),
        "qaRunIds": qa_run_ids,
        "skillCallIds": skill_call_ids,
        "summaryVersion": trace_summaries[-1]["summaryVersion"],
        "invocationCount": len(invocation_rows),
        "citationCount": len(cited_chunk_ids),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
