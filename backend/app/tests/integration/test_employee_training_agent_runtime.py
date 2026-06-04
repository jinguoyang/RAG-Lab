"""员工培训 Agent 平台侧计划、题库和课堂运行测试。"""

from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.training_classroom import (
    ClassroomEventSubmitRequest,
    ClassroomSessionCreateRequest,
)
from app.schemas.training_plan import PlanDraftRequest
from app.schemas.training_question import QuestionDraftRequest
from app.services.app_runtime_service import _hash_api_key
from app.tables import (
    chunks,
    config_revisions,
    knowledge_bases,
    rag_app_api_keys,
    rag_apps,
    training_classroom_messages,
    training_classroom_sessions,
    training_plans,
    training_questions,
    users,
)


def _insert_training_app(db):
    """插入员工培训 Agent 平台接口所需的最小 App、KB、Revision、Key 和 Chunk。"""
    now = datetime.now(UTC)
    owner_id = uuid4()
    kb_id = uuid4()
    revision_id = uuid4()
    app_id = uuid4()
    plain_key = "rlak_training_agent_platform"
    db.execute(
        users.insert().values(
            user_id=owner_id,
            username="training-agent-owner",
            display_name="Training Agent Owner",
            email="training-agent@example.com",
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
            name="员工培训知识库",
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
            pipeline_definition={
                "version": "1.0",
                "templateId": "employee-training-v1",
                "nodes": [{"type": "denseRetrieval", "enabled": True}],
            },
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
            default_config_revision_id=revision_id,
            name="员工培训助手",
            description=None,
            status="active",
            output_policy={},
            metadata={
                "scenario": {
                    "scenarioType": "employee_training",
                    "scenarioTemplateId": "builtin_employee_training_v1",
                    "scenarioConfig": {"passingScore": 80, "questionCount": 3},
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
            api_key_id=uuid4(),
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
    for index, (heading, content) in enumerate(
        [
            ("现场安全制度", "现场安全员必须掌握入场检查、风险辨识和事故上报流程。"),
            ("设备点检SOP", "设备点检人员需要按照点检表确认状态，异常时立即停机并记录。"),
        ],
        start=1,
    ):
        db.execute(
            chunks.insert().values(
                chunk_id=uuid4(),
                version_id=uuid4(),
                document_id=uuid4(),
                kb_id=kb_id,
                chunk_index=index,
                section=heading,
                page_no=index,
                content=content,
                content_hash=f"training-agent-{index}",
                token_count=None,
                status="active",
                metadata={"documentName": heading},
                created_at=now,
                chunk_revision_id=None,
                parse_revision_id=None,
                document_version_id=None,
                start_offset=None,
                end_offset=None,
                section_path=None,
                heading=heading,
                summary=None,
                retired_at=None,
                retired_by=None,
                deleted_at=None,
                deleted_by=None,
            )
        )
    return plain_key, str(app_id)


def test_plan_draft_uses_kb_evidence_and_persists_platform_plan(db):
    """学习计划草稿应来自当前 App 知识库证据，并保存平台侧草稿。"""
    credential, app_id = _insert_training_app(db)

    from app.services.training_plan_service import create_plan_draft

    response = create_plan_draft(
        db,
        credential,
        PlanDraftRequest(jobTitle="现场安全员", jobDescription="负责入场检查和风险辨识"),
    )

    assert response.planId
    assert response.documents[0].title == "现场安全制度"
    assert response.evidenceChunkIds
    assert response.readingOrder == [doc.documentId for doc in response.documents]
    assert db.execute(training_plans.select()).mappings().one()["app_id"] == app_id


def test_question_drafts_include_choice_true_false_and_subjective(db):
    """题库草稿应覆盖判断、选择和主观题，并保存平台题库草稿。"""
    credential, app_id = _insert_training_app(db)

    from app.services.training_question_service import create_question_drafts

    response = create_question_drafts(
        db,
        credential,
        QuestionDraftRequest(planId=str(uuid4()), jobTitle="现场安全员", count=3),
    )

    assert {item.questionType for item in response} == {"single_choice", "true_false", "subjective"}
    assert response[0].evidenceChunkIds
    assert db.execute(training_questions.select()).mappings().all()


def test_classroom_event_returns_structured_actions_and_records_context(db):
    """课堂流程由平台状态机控制，并返回结构化 uiActions。"""
    credential, app_id = _insert_training_app(db)

    from app.services.training_classroom_service import create_classroom_session, submit_classroom_event

    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(endUserId="employee-001", inputs={"jobTitle": "现场安全员"}),
    )
    plan_response = submit_classroom_event(
        db,
        credential,
        created.sessionId,
        ClassroomEventSubmitRequest(eventType="start", payload={}),
    )
    teach_response = submit_classroom_event(
        db,
        credential,
        created.sessionId,
        ClassroomEventSubmitRequest(eventType="continue", payload={}),
    )

    assert plan_response.classroomState == "PLAN"
    assert teach_response.classroomState == "TEACH"
    assert teach_response.uiActions[0].actionType == "button_group"
    session_row = db.execute(training_classroom_sessions.select()).mappings().one()
    assert session_row["current_state"] == "TEACH"
    message_rows = db.execute(training_classroom_messages.select()).mappings().all()
    assert [row["role"] for row in message_rows] == ["assistant", "assistant"]


def test_classroom_continue_from_teach_enters_check_understand(db):
    """教学讲解完成后应先进入理解确认，而不是直接跳到测验。"""
    credential, app_id = _insert_training_app(db)

    from app.services.training_classroom_service import create_classroom_session, submit_classroom_event

    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(endUserId="employee-001", inputs={"jobTitle": "现场安全员"}),
    )
    submit_classroom_event(db, credential, created.sessionId, ClassroomEventSubmitRequest(eventType="start", payload={}))
    submit_classroom_event(db, credential, created.sessionId, ClassroomEventSubmitRequest(eventType="continue", payload={}))

    response = submit_classroom_event(
        db,
        credential,
        created.sessionId,
        ClassroomEventSubmitRequest(eventType="continue", payload={}),
    )

    assert response.classroomState == "CHECK_UNDERSTAND"
    assert response.control.requiresInput is True
    assert response.uiActions[0].actionType == "button_group"


def test_classroom_scores_answer_from_server_question_not_client_payload(db):
    """评分必须以平台题库答案为准，不能信任客户端传入的 correctAnswer。"""
    credential, app_id = _insert_training_app(db)

    from app.services.training_classroom_service import create_classroom_session, submit_classroom_event

    now = datetime.now(UTC)
    question_id = uuid4()
    db.execute(
        training_questions.insert().values(
            question_id=question_id,
            plan_id=uuid4(),
            app_id=app_id,
            question_type="single_choice",
            category="practice",
            content="请选择正确操作。",
            options=[{"label": "A", "text": "按流程记录"}, {"label": "B", "text": "跳过记录"}],
            correct_answer="A",
            explanation="必须按流程记录。",
            rubric=None,
            evidence_chunk_ids=[],
            status="approved",
            metadata={},
            created_at=now,
            created_by=None,
            updated_at=now,
            updated_by=None,
        )
    )
    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(endUserId="employee-001", inputs={"jobTitle": "现场安全员"}),
    )
    db.execute(
        training_classroom_sessions.update()
        .where(training_classroom_sessions.c.session_id == created.sessionId)
        .values(current_state="QUIZ")
    )
    db.commit()

    response = submit_classroom_event(
        db,
        credential,
        created.sessionId,
        ClassroomEventSubmitRequest(
            eventType="submit_answer",
            payload={"questionId": str(question_id), "answer": "B", "correctAnswer": "B"},
        ),
    )

    assert response.classroomState == "GRADE"
    assert "得分：0" in response.visibleContent


def test_classroom_rejects_illegal_finish_command_during_teach(db):
    """用户用文本要求结束课程时，控制器应拒绝而不是正常教学回答。"""
    credential, app_id = _insert_training_app(db)

    from app.services.training_classroom_service import create_classroom_session, submit_classroom_event

    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(endUserId="employee-001", inputs={"jobTitle": "现场安全员"}),
    )
    db.execute(
        training_classroom_sessions.update()
        .where(training_classroom_sessions.c.session_id == created.sessionId)
        .values(current_state="TEACH")
    )
    db.commit()

    response = submit_classroom_event(
        db,
        credential,
        created.sessionId,
        ClassroomEventSubmitRequest(eventType="query", payload={}, query="本节课结束"),
    )

    assert response.eventType == "invalid_command"
    assert response.classroomState == "TEACH"
    assert "不允许" in response.visibleContent


def test_classroom_routes_unrelated_question_to_off_topic(db):
    """明显偏离课程的问题应进入 OFF_TOPIC，并提示回到课程内容。"""
    credential, app_id = _insert_training_app(db)

    from app.services.training_classroom_service import create_classroom_session, submit_classroom_event

    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(endUserId="employee-001", inputs={"jobTitle": "现场安全员"}),
    )
    db.execute(
        training_classroom_sessions.update()
        .where(training_classroom_sessions.c.session_id == created.sessionId)
        .values(current_state="TEACH")
    )
    db.commit()

    response = submit_classroom_event(
        db,
        credential,
        created.sessionId,
        ClassroomEventSubmitRequest(eventType="query", payload={}, query="今天股票行情怎么样"),
    )

    assert response.eventType == "off_topic"
    assert response.classroomState == "OFF_TOPIC"
    assert "回到当前课程" in response.visibleContent
