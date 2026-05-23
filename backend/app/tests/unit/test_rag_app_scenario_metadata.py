"""RAG App 场景元数据测试。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.schemas.rag_app import RagAppCreateRequest
from app.services.rag_app_service import create_rag_app, get_rag_app
from app.tables import config_revisions, knowledge_bases, rag_apps


def _insert_active_kb(db, owner_id):
    """插入一个可创建应用的 active 知识库。"""
    kb_id = uuid4()
    now = datetime.now(UTC)
    db.execute(
        knowledge_bases.insert().values(
            kb_id=kb_id,
            name="场景知识库",
            description=None,
            owner_id=owner_id,
            sparse_index_enabled=False,
            graph_index_enabled=False,
            sparse_required_for_activation=False,
            graph_required_for_activation=False,
            status="active",
            active_config_revision_id=None,
            metadata={},
            created_at=now,
            created_by=owner_id,
            updated_at=now,
            updated_by=owner_id,
        )
    )
    return kb_id


def _insert_saved_revision(db, kb_id, owner_id):
    """插入一个可被 RAG App 绑定的 saved 配置版本。"""
    revision_id = uuid4()
    now = datetime.now(UTC)
    db.execute(
        config_revisions.insert().values(
            config_revision_id=revision_id,
            kb_id=kb_id,
            revision_no=1,
            source_template_id=None,
            status="saved",
            pipeline_definition={
                "version": "1.0",
                "mode": "constrained-stage-pipeline",
                "templateId": "system_default",
                "nodes": [],
            },
            validation_snapshot={"valid": True, "errors": [], "warnings": []},
            remark=None,
            activated_at=None,
            activated_by=None,
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
    return revision_id


def test_create_rag_app_persists_scenario_metadata(db, admin_user):
    """创建应用时应保存并返回场景字段，底层仍落入 metadata.scenario。"""
    owner_id = uuid4()
    kb_id = _insert_active_kb(db, owner_id)
    revision_id = _insert_saved_revision(db, kb_id, owner_id)

    created = create_rag_app(
        db,
        admin_user,
        RagAppCreateRequest(
            name="员工培训助手",
            kbId=kb_id,
            defaultConfigRevisionId=revision_id,
            scenarioType="employee_training",
            scenarioTemplateId="builtin_employee_training_v1",
            scenarioConfig={"questionCount": 5, "passingScore": 80},
            publishChannels={"api": True, "embed": False},
            embedSettings={"enabled": False, "allowedOrigins": []},
        ),
    )

    assert created.scenarioType == "employee_training"
    assert created.scenarioTemplateId == "builtin_employee_training_v1"
    assert created.scenarioConfig["questionCount"] == 5
    assert created.publishChannels == {"api": True, "embed": False}
    assert created.embedSettings["enabled"] is False

    row = db.execute(rag_apps.select().where(rag_apps.c.app_id == UUID(created.appId))).mappings().one()
    assert row["metadata"]["scenario"]["scenarioType"] == "employee_training"


def test_get_rag_app_defaults_legacy_app_to_knowledge_qa(db, admin_user):
    """旧应用缺少场景 metadata 时，管理端 DTO 应兼容为知识库问答助手。"""
    owner_id = uuid4()
    kb_id = _insert_active_kb(db, owner_id)
    app_id = uuid4()
    now = datetime.now(UTC)
    db.execute(
        rag_apps.insert().values(
            app_id=app_id,
            kb_id=kb_id,
            default_config_revision_id=None,
            name="旧应用",
            description=None,
            status="active",
            output_policy={},
            metadata={},
            created_at=now,
            created_by=owner_id,
            updated_at=now,
            updated_by=owner_id,
            deleted_at=None,
            deleted_by=None,
        )
    )

    app = get_rag_app(db, admin_user, app_id)

    assert app.scenarioType == "knowledge_qa"
    assert app.scenarioTemplateId == "builtin_knowledge_qa_v1"
    assert app.scenarioConfig["noEvidencePolicy"] == "refuse"
    assert app.publishChannels["api"] is True
