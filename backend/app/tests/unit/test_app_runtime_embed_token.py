"""App Runtime Embed Token 和 retrieve 单元测试。"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.app_runtime import AppRuntimeEmbedTokenRequest, AppRuntimeRetrieveRequest
from app.services.app_runtime_service import (
    AppRuntimeAuthError,
    create_app_runtime_embed_token,
    retrieve_app_runtime_evidence,
)
from app.services.app_runtime_service import _hash_api_key
from app.tables import chunks, config_revisions, knowledge_bases, rag_app_api_keys, rag_apps, users


def _insert_runtime_app(db, owner_id):
    """插入可运行的知识库、配置版本、应用和 API Key。"""
    now = datetime.now(UTC)
    kb_id = uuid4()
    revision_id = uuid4()
    app_id = uuid4()
    api_key_id = uuid4()
    plain_key = "rlak_test_embed_token"
    db.execute(
        users.insert().values(
            user_id=owner_id,
            username="runtime-owner",
            display_name="Runtime Owner",
            email="runtime@example.com",
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
            name="嵌入知识库",
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
            name="知识问答助手",
            description=None,
            status="active",
            output_policy={},
            metadata={"scenario": {"scenarioType": "knowledge_qa"}},
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
    return plain_key, app_id, kb_id


def test_embed_token_can_be_used_for_retrieve(db):
    """短期 Token 可用于 retrieve，且证据只返回摘要。"""
    owner_id = uuid4()
    api_key, app_id, kb_id = _insert_runtime_app(db, owner_id)
    chunk_id = uuid4()
    db.execute(
        chunks.insert().values(
            chunk_id=chunk_id,
            version_id=uuid4(),
            document_id=uuid4(),
            kb_id=kb_id,
            chunk_index=1,
            section="入职",
            page_no=1,
            content="员工入职培训需要完成安全制度学习，并在系统中提交确认。" * 8,
            content_hash="hash",
            token_count=None,
            status="active",
            metadata={},
            created_at=datetime.now(UTC),
            chunk_revision_id=None,
            parse_revision_id=None,
            document_version_id=None,
            start_offset=None,
            end_offset=None,
            section_path=None,
            heading="制度文档",
            summary=None,
            retired_at=None,
            retired_by=None,
            deleted_at=None,
            deleted_by=None,
        )
    )

    token_response = create_app_runtime_embed_token(db, api_key, AppRuntimeEmbedTokenRequest(ttlSeconds=300))
    result = retrieve_app_runtime_evidence(
        db,
        token_response.embedToken,
        AppRuntimeRetrieveRequest(query="入职培训", topK=3),
    )

    assert token_response.appId == str(app_id)
    assert token_response.embedToken.startswith("rlet_")
    assert result.appId == str(app_id)
    assert result.kbId == str(kb_id)
    assert len(result.evidences) == 1
    assert result.evidences[0].chunkId == str(chunk_id)
    assert len(result.evidences[0].summary) < 260
    assert result.metadata["authType"] == "embedToken"


def test_tampered_embed_token_is_rejected(db):
    """篡改短期 Token 后签名校验失败。"""
    owner_id = uuid4()
    api_key, _, _ = _insert_runtime_app(db, owner_id)
    token_response = create_app_runtime_embed_token(db, api_key, AppRuntimeEmbedTokenRequest(ttlSeconds=300))

    with pytest.raises(AppRuntimeAuthError):
        retrieve_app_runtime_evidence(
            db,
            f"{token_response.embedToken}x",
            AppRuntimeRetrieveRequest(query="任意问题"),
        )
