"""三方 LLM 调用统一审计服务测试。"""
from datetime import UTC, datetime

from sqlalchemy import select

from app.services.app_runtime_service import _resolve_runtime_context_without_quota
from app.services.app_llm_audit_service import begin_app_llm_invocation, finish_app_llm_invocation
from app.tables import app_conversations, app_invocations, app_messages, rag_app_api_keys
from app.tests.integration.test_employee_training_agent_runtime import _insert_training_app


def test_begin_and_finish_app_llm_invocation_records_conversation_messages_and_invocation(db):
    """非聊天 LLM 调用应复用 Runtime 会话、消息和 invocation 审计主线。"""
    credential, app_id = _insert_training_app(db)
    context = _resolve_runtime_context_without_quota(db, credential, datetime.now(UTC))

    audit = begin_app_llm_invocation(
        db,
        context,
        endpoint="/api/v1/training/plans/drafts",
        operation="buildLearningPlanDraft",
        skill_name="buildLearningPlanDraft",
        input_summary={"jobTitle": "安全员", "jobDescriptionLength": 4},
        user_content={"jobTitle": "安全员"},
    )
    finish_app_llm_invocation(
        db,
        audit,
        status="success",
        assistant_content={"planId": "plan-001", "abilityGroupCount": 2},
        response_summary={"planId": "plan-001", "fallback": False},
    )

    conversation = db.execute(select(app_conversations)).mappings().one()
    assert str(conversation["app_id"]) == app_id
    assert conversation["metadata"]["source"] == "external_llm_api"
    assert conversation["metadata"]["operation"] == "buildLearningPlanDraft"

    messages = db.execute(select(app_messages).order_by(app_messages.c.created_at)).mappings().all()
    assert [row["role"] for row in messages] == ["user", "assistant"]
    assert messages[0]["metadata"]["operation"] == "buildLearningPlanDraft"
    assert messages[1]["metadata"]["operation"] == "buildLearningPlanDraft"

    invocation = db.execute(select(app_invocations)).mappings().one()
    assert str(invocation["app_id"]) == app_id
    assert invocation["conversation_id"] == conversation["conversation_id"]
    assert invocation["message_id"] == messages[1]["message_id"]
    assert invocation["status"] == "success"
    assert invocation["request_summary"]["operation"] == "buildLearningPlanDraft"
    assert invocation["response_summary"]["planId"] == "plan-001"

    key_row = db.execute(select(rag_app_api_keys)).mappings().one()
    assert key_row["last_used_at"] is not None
