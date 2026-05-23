"""RAG App 场景元数据测试。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.schemas.rag_app import RagAppCreateRequest
from app.services.rag_app_service import create_rag_app, get_rag_app, get_rag_app_training_report
from app.tables import app_conversations, app_messages, config_revisions, knowledge_bases, rag_apps


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


def test_get_rag_app_training_report_aggregates_training_results(db, admin_user):
    """培训报告只聚合同一应用下写入 metadata.trainingResult 的助手消息。"""
    owner_id = uuid4()
    kb_id = _insert_active_kb(db, owner_id)
    revision_id = _insert_saved_revision(db, kb_id, owner_id)
    app = create_rag_app(
        db,
        admin_user,
        RagAppCreateRequest(
            name="员工培训助手",
            kbId=kb_id,
            defaultConfigRevisionId=revision_id,
            scenarioType="employee_training",
            scenarioTemplateId="builtin_employee_training_v1",
        ),
    )
    app_id = UUID(app.appId)
    other_app_id = uuid4()
    now = datetime.now(UTC)
    first_conversation_id = uuid4()
    second_conversation_id = uuid4()
    other_conversation_id = uuid4()
    db.execute(
        app_conversations.insert(),
        [
            {
                "conversation_id": first_conversation_id,
                "app_id": app_id,
                "end_user_id": "u-1",
                "status": "active",
                "metadata": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "conversation_id": second_conversation_id,
                "app_id": app_id,
                "end_user_id": "u-2",
                "status": "active",
                "metadata": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "conversation_id": other_conversation_id,
                "app_id": other_app_id,
                "end_user_id": "u-3",
                "status": "active",
                "metadata": {},
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    db.execute(
        app_messages.insert(),
        [
            {
                "message_id": uuid4(),
                "conversation_id": first_conversation_id,
                "role": "assistant",
                "content": "训练报告 1",
                "qa_run_id": uuid4(),
                "status": "success",
                "metadata": {"trainingResult": {"score": 100, "passed": True, "passingScore": 80}},
                "created_at": now,
            },
            {
                "message_id": uuid4(),
                "conversation_id": second_conversation_id,
                "role": "assistant",
                "content": "训练报告 2",
                "qa_run_id": uuid4(),
                "status": "success",
                "metadata": {"trainingResult": {"score": 50, "passed": False, "passingScore": 80}},
                "created_at": now,
            },
            {
                "message_id": uuid4(),
                "conversation_id": second_conversation_id,
                "role": "assistant",
                "content": "普通消息",
                "qa_run_id": None,
                "status": "success",
                "metadata": {},
                "created_at": now,
            },
            {
                "message_id": uuid4(),
                "conversation_id": other_conversation_id,
                "role": "assistant",
                "content": "其他应用训练报告",
                "qa_run_id": uuid4(),
                "status": "success",
                "metadata": {"trainingResult": {"score": 0, "passed": False, "passingScore": 80}},
                "created_at": now,
            },
        ],
    )

    report = get_rag_app_training_report(db, admin_user, app_id)

    assert report.appId == str(app_id)
    assert report.totalSubmissions == 2
    assert report.passedSubmissions == 1
    assert report.failedSubmissions == 1
    assert report.averageScore == 75
    assert report.passRate == 0.5
    assert len(report.recentResults) == 2
