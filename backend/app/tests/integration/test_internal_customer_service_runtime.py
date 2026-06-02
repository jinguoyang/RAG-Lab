"""内部客服 Runtime 集成测试。"""
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage
from sqlalchemy import select

from app.core.config import get_settings
from app.schemas.app_runtime import AppRuntimeChatRequest
from app.services.app_runtime_service import _hash_api_key, chat_with_app_runtime
from app.tables import (
    app_invocations,
    config_revisions,
    knowledge_bases,
    rag_app_api_keys,
    rag_apps,
    training_skill_calls,
    users,
)


@pytest.fixture(autouse=True)
def _enable_primary_runtime(monkeypatch):
    """客服 Primary 集成测试显式开启新链路，避免依赖默认配置。"""
    monkeypatch.setenv("RAG_LAB_AGENT_RUNTIME_ENABLED", "true")
    monkeypatch.setenv("RAG_LAB_AGENT_RUNTIME_DEFAULT_VERSION", "langgraph_primary_v1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeRagAgent:
    """测试 Agent：真实调用 Tool，避免集成测试依赖网络 Provider。"""

    def __init__(self, qa_run_tool):
        self.qa_run_tool = qa_run_tool

    def invoke(self, payload, config):
        query = payload["messages"][-1]["content"]
        tool_result = self.qa_run_tool.invoke({"query": query})
        return {"messages": [AIMessage(content=tool_result["answer"])]}


def _build_fake_rag_agent(**kwargs):
    """按生产工厂签名构建测试 Agent。"""
    return _FakeRagAgent(kwargs["qa_run_tool"])


class _FakeRagAgentWithoutTool:
    """模拟模型基于上下文直接回答，用于验证 Runtime Tool 守卫。"""

    def invoke(self, payload, config):
        return {"messages": [AIMessage(content="未经 Tool 校验的上下文草稿")]}


def _build_fake_rag_agent_without_tool(**kwargs):
    """构建跳过 Tool 的测试 Agent。"""
    return _FakeRagAgentWithoutTool()


def _insert_knowledge_qa_app(db, owner_id):
    """插入 knowledge_qa 场景应用。"""
    now = datetime.now(UTC)
    kb_id = uuid4()
    revision_id = uuid4()
    app_id = uuid4()
    api_key_id = uuid4()
    plain_key = "rlak_test_cs_graph"

    db.execute(
        users.insert().values(
            user_id=owner_id,
            username="cs-owner",
            display_name="CS Owner",
            email="cs@example.com",
            platform_role="platform_admin",
            security_level="internal",
            status="active",
            last_login_at=None,
            created_at=now,
            created_by=None,
            updated_at=now,
            updated_by=None,
            deleted_at=None,
            deleted_by=None,
        )
    )
    db.execute(
        knowledge_bases.insert().values(
            kb_id=kb_id,
            name="客服知识库",
            description=None,
            owner_id=owner_id,
            sparse_index_enabled=False,
            graph_index_enabled=False,
            sparse_required_for_activation=False,
            graph_required_for_activation=False,
            status="active",
            active_config_revision_id=revision_id,
            metadata={},
            created_at=now,
            created_by=owner_id,
            updated_at=now,
            updated_by=owner_id,
        )
    )
    db.execute(
        config_revisions.insert().values(
            config_revision_id=revision_id,
            kb_id=kb_id,
            revision_no=1,
            source_template_id=None,
            status="active",
            pipeline_definition={"version": "1.0", "templateId": "system_default", "nodes": []},
            validation_snapshot={"valid": True, "errors": [], "warnings": []},
            remark=None,
            activated_at=now,
            activated_by=owner_id,
            deactivated_at=None,
            deactivated_by=None,
            created_at=now,
            created_by=owner_id,
            updated_at=now,
            updated_by=owner_id,
            deleted_at=None,
            deleted_by=None,
        )
    )
    db.execute(
        rag_apps.insert().values(
            app_id=app_id,
            kb_id=kb_id,
            default_config_revision_id=None,
            name="内部客服助手",
            description=None,
            status="active",
            output_policy={},
            metadata={
                "scenario": {
                    "scenarioType": "knowledge_qa",
                    "scenarioConfig": {"noEvidencePolicy": "refuse"},
                }
            },
            created_at=now,
            created_by=owner_id,
            updated_at=now,
            updated_by=owner_id,
            deleted_at=None,
            deleted_by=None,
        )
    )
    db.execute(
        rag_app_api_keys.insert().values(
            api_key_id=api_key_id,
            app_id=app_id,
            key_hash=_hash_api_key(plain_key),
            key_prefix=plain_key[:16],
            status="active",
            expires_at=None,
            last_used_at=None,
            created_at=now,
            created_by=owner_id,
            revoked_at=None,
            revoked_by=None,
        )
    )
    db.commit()
    return plain_key, app_id, kb_id


class TestCustomerServiceRuntime:
    """knowledge_qa 场景通过客服 Graph 路由的集成测试。"""

    @pytest.fixture()
    def knowledge_qa_app(self, db, test_user):
        owner_id = uuid4()
        plain_key, app_id, kb_id = _insert_knowledge_qa_app(db, owner_id)

        class AppInfo:
            pass

        info = AppInfo()
        info.credential = plain_key
        info.app_id = app_id
        info.kb_id = kb_id
        return info

    def test_customer_service_graph_routes_knowledge_qa(self, db, knowledge_qa_app):
        """knowledge_qa 应用应通过客服 Graph 路由，返回 Graph 元数据。"""
        mock_run_id = str(uuid4())
        mock_qa_detail = type("Detail", (), {
            "runId": mock_run_id,
            "answer": "请按制度提交申请。",
            "status": "success",
            "citations": [
                type("Citation", (), {
                    "citationId": "c1",
                    "evidenceId": "e1",
                    "label": "制度",
                    "locationSnapshot": {"chunkId": "chunk-1"},
                })(),
            ],
            "metrics": {},
        })()

        with patch("app.services.app_runtime_service.create_qa_run") as mock_create, \
             patch("app.services.app_runtime_service.get_qa_run_detail") as mock_detail, \
             patch("app.services.agent_runtime.model_adapter.create_chat_model", return_value=object()), \
             patch("app.services.agent_runtime.rag_agent_factory.build_rag_answer_agent", side_effect=_build_fake_rag_agent), \
             patch("app.services.agent_runtime.runtime_facade._get_shared_checkpointer", return_value=InMemorySaver()):
            mock_create.return_value = type("Resp", (), {"runId": mock_run_id})()
            mock_detail.return_value = mock_qa_detail

            response = chat_with_app_runtime(
                db,
                knowledge_qa_app.credential,
                AppRuntimeChatRequest(query="如何提交申请？", endUserId="user-1"),
            )

        assert response.answer == "请按制度提交申请。"
        assert response.metadata["runtimeVersion"] == "langgraph_primary_v1"
        assert response.metadata["threadId"] == response.conversationId
        assert len(response.citations) == 1
        assert response.citations[0].locationSnapshot.get("chunkId") == "chunk-1"

        invocation = db.execute(
            select(app_invocations).where(app_invocations.c.app_id == knowledge_qa_app.app_id)
        ).mappings().one()
        summary = invocation["response_summary"]
        assert summary["agentInvocationId"] == str(invocation["invocation_id"])
        assert summary["threadId"] == response.conversationId
        assert summary["checkpointId"] == response.metadata["checkpointId"]
        assert summary["qaRunId"] == mock_run_id
        assert summary["skillCallId"]
        assert summary["modelCallId"]
        assert summary["summaryVersion"] == 0
        skill_call = db.execute(
            select(training_skill_calls).where(
                training_skill_calls.c.skill_call_id == summary["skillCallId"]
            )
        ).mappings().one()
        assert skill_call["skill_name"] == "query_knowledge_base"

    def test_customer_service_graph_refuses_without_citations(self, db, knowledge_qa_app):
        """无证据时应拒答。"""
        mock_run_id = str(uuid4())
        mock_qa_detail = type("Detail", (), {
            "runId": mock_run_id,
            "answer": "猜测回答",
            "status": "success",
            "citations": [],
            "metrics": {},
        })()

        with patch("app.services.app_runtime_service.create_qa_run") as mock_create, \
             patch("app.services.app_runtime_service.get_qa_run_detail") as mock_detail, \
             patch("app.services.agent_runtime.model_adapter.create_chat_model", return_value=object()), \
             patch("app.services.agent_runtime.rag_agent_factory.build_rag_answer_agent", side_effect=_build_fake_rag_agent), \
             patch("app.services.agent_runtime.runtime_facade._get_shared_checkpointer", return_value=InMemorySaver()):
            mock_create.return_value = type("Resp", (), {"runId": mock_run_id})()
            mock_detail.return_value = mock_qa_detail

            response = chat_with_app_runtime(
                db,
                knowledge_qa_app.credential,
                AppRuntimeChatRequest(query="未知问题", endUserId="user-1"),
            )

        assert "没有足够依据" in response.answer
        assert response.citations == []

    def test_customer_service_guard_returns_authorized_qa_run_answer(self, db, knowledge_qa_app):
        """模型跳过 Tool 时，守卫模式必须返回 QARun 授权回答而非模型草稿。"""
        mock_run_id = str(uuid4())
        mock_qa_detail = type("Detail", (), {
            "runId": mock_run_id,
            "answer": "经过 QARun 校验的制度回答。",
            "status": "success",
            "citations": [
                type("Citation", (), {
                    "citationId": "c1",
                    "evidenceId": "e1",
                    "label": "制度",
                    "locationSnapshot": {"chunkId": "chunk-1"},
                })(),
            ],
            "metrics": {},
        })()

        with patch("app.services.app_runtime_service.create_qa_run") as mock_create, \
             patch("app.services.app_runtime_service.get_qa_run_detail") as mock_detail, \
             patch("app.services.agent_runtime.model_adapter.create_chat_model", return_value=object()), \
             patch("app.services.agent_runtime.rag_agent_factory.build_rag_answer_agent", side_effect=_build_fake_rag_agent_without_tool), \
             patch("app.services.agent_runtime.runtime_facade._get_shared_checkpointer", return_value=InMemorySaver()):
            mock_create.return_value = type("Resp", (), {"runId": mock_run_id})()
            mock_detail.return_value = mock_qa_detail

            response = chat_with_app_runtime(
                db,
                knowledge_qa_app.credential,
                AppRuntimeChatRequest(query="继续追问", endUserId="user-1"),
            )

        assert response.answer == "经过 QARun 校验的制度回答。"
        invocation = db.execute(
            select(app_invocations).where(app_invocations.c.app_id == knowledge_qa_app.app_id)
        ).mappings().one()
        assert invocation["response_summary"]["toolInvocationMode"] == "guard"
