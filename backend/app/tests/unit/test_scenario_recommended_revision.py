"""场景推荐配置版本测试。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.schemas.rag_app import RagAppCreateRequest
from app.services.rag_app_service import create_rag_app
from app.tables import config_revisions, knowledge_bases


def test_create_rag_app_can_create_saved_scenario_revision(db, admin_user):
    """创建场景应用时可生成专属 saved Revision，且不改变 KB active revision。"""
    owner_id = uuid4()
    kb_id = uuid4()
    active_revision_id = uuid4()
    now = datetime.now(UTC)
    db.execute(
        knowledge_bases.insert().values(
            kb_id=kb_id,
            name="培训知识库",
            description=None,
            owner_id=owner_id,
            sparse_index_enabled=False,
            graph_index_enabled=False,
            sparse_required_for_activation=False,
            graph_required_for_activation=False,
            status="active",
            active_config_revision_id=active_revision_id,
            metadata={},
            created_at=now,
            created_by=owner_id,
            updated_at=now,
            updated_by=owner_id,
        )
    )
    db.execute(
        config_revisions.insert().values(
            config_revision_id=active_revision_id,
            kb_id=kb_id,
            revision_no=1,
            source_template_id=None,
            status="active",
            pipeline_definition={"version": "1.0", "templateId": "system_default", "nodes": []},
            validation_snapshot={"valid": True, "errors": [], "warnings": []},
            remark="active baseline",
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

    app = create_rag_app(
        db,
        admin_user,
        RagAppCreateRequest(
            name="培训助手",
            kbId=kb_id,
            scenarioType="employee_training",
            scenarioTemplateId="builtin_employee_training_v1",
            createRecommendedConfigRevision=True,
        ),
    )

    assert app.defaultConfigRevisionId is not None
    assert app.defaultConfigRevisionId != str(active_revision_id)

    kb_row = db.execute(
        knowledge_bases.select().where(knowledge_bases.c.kb_id == kb_id)
    ).mappings().one()
    assert kb_row["active_config_revision_id"] == str(active_revision_id)

    revision_row = db.execute(
        config_revisions.select().where(config_revisions.c.config_revision_id == UUID(app.defaultConfigRevisionId))
    ).mappings().one()
    assert revision_row["status"] == "saved"
    assert revision_row["revision_no"] == 2
    assert revision_row["pipeline_definition"]["templateId"] == "builtin_employee_training_v1"
    assert revision_row["pipeline_definition"]["scenarioType"] == "employee_training"
