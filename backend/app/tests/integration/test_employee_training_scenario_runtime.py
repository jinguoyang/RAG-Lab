"""员工培训助手 Runtime 集成测试。"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.schemas.app_runtime import (
    AppRuntimeStructuredRunRequest,
    AppRuntimeTrainingQuizSubmissionRequest,
)
from app.services.app_runtime_service import (
    _hash_api_key,
    create_app_runtime_structured_run,
    submit_app_runtime_training_quiz,
)
from app.tables import (
    app_messages,
    chunks,
    config_revisions,
    knowledge_bases,
    rag_app_api_keys,
    rag_apps,
    users,
)


def _insert_training_app(db, owner_id):
    """插入员工培训助手运行所需的最小 App、KB、Revision 和 Key。"""
    now = datetime.now(UTC)
    kb_id = uuid4()
    revision_id = uuid4()
    app_id = uuid4()
    api_key_id = uuid4()
    plain_key = "rlak_test_employee_training"
    db.execute(
        users.insert().values(
            user_id=owner_id,
            username="training-owner",
            display_name="Training Owner",
            email="training@example.com",
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
            name="培训知识库",
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
            pipeline_definition={"version": "1.0", "templateId": "employee-training-v1", "nodes": []},
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
            name="员工培训助手",
            description=None,
            status="active",
            output_policy={},
            metadata={
                "scenario": {
                    "scenarioType": "employee_training",
                    "scenarioConfig": {"questionCount": 2, "passingScore": 80, "recordTrainingResult": True},
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
    db.execute(
        chunks.insert().values(
            chunk_id=uuid4(),
            version_id=uuid4(),
            document_id=uuid4(),
            kb_id=kb_id,
            chunk_index=1,
            section="安全制度",
            page_no=1,
            content="员工进入现场前必须完成安全培训，并通过测验后方可上岗。",
            content_hash="training-hash",
            token_count=None,
            status="active",
            metadata={},
            created_at=now,
            chunk_revision_id=None,
            parse_revision_id=None,
            document_version_id=None,
            start_offset=None,
            end_offset=None,
            section_path=None,
            heading="安全制度",
            summary=None,
            retired_at=None,
            retired_by=None,
            deleted_at=None,
            deleted_by=None,
        )
    )
    return plain_key, app_id, kb_id


def _patch_qa_run(monkeypatch, run_id):
    """替换 QA 执行，避免集成测试依赖真实模型 Provider。"""

    def fake_create_qa_run(*args, **kwargs):
        return SimpleNamespace(runId=str(run_id))

    def fake_get_qa_run_detail(*args, **kwargs):
        return SimpleNamespace(
            runId=str(run_id),
            status="success",
            answer="现场安全培训要求员工先学习制度，再完成测验。",
            citations=[],
            metrics={"latencyMs": 12, "tokenUsage": {"total": 24}},
        )

    monkeypatch.setattr("app.services.app_runtime_service.create_qa_run", fake_create_qa_run)
    monkeypatch.setattr("app.services.app_runtime_service.get_qa_run_detail", fake_get_qa_run_detail)


def test_structured_run_generates_training_quiz_and_message_metadata(db, monkeypatch):
    """结构化测验生成应回溯 QARun，并把题目写入助手消息 metadata。"""
    api_key, app_id, _ = _insert_training_app(db, uuid4())
    run_id = uuid4()
    _patch_qa_run(monkeypatch, run_id)

    response = create_app_runtime_structured_run(
        db,
        api_key,
        AppRuntimeStructuredRunRequest(
            action="training_quiz_generate",
            topic="现场安全",
            questionCount=2,
            difficulty="normal",
        ),
    )

    assert response.appId == str(app_id)
    assert response.action == "training_quiz_generate"
    assert response.runId == str(run_id)
    assert response.output["quiz"]["questionCount"] == 2
    assert len(response.output["quiz"]["questions"]) == 2

    message = db.execute(app_messages.select().where(app_messages.c.message_id == UUID(response.messageId))).mappings().one()
    assert message["qa_run_id"] == str(run_id)
    assert message["metadata"]["trainingStructuredRun"]["action"] == "training_quiz_generate"
    assert message["metadata"]["trainingStructuredRun"]["quiz"]["questions"][0]["correctAnswer"]


def test_quiz_submission_scores_answers_and_records_training_result(db, monkeypatch):
    """答题提交应评分，并把训练结果写入 AppMessage metadata.trainingResult。"""
    api_key, _, _ = _insert_training_app(db, uuid4())
    run_id = uuid4()
    _patch_qa_run(monkeypatch, run_id)
    quiz_response = create_app_runtime_structured_run(
        db,
        api_key,
        AppRuntimeStructuredRunRequest(action="training_quiz_generate", topic="现场安全", questionCount=2),
    )
    questions = quiz_response.output["quiz"]["questions"]

    response = submit_app_runtime_training_quiz(
        db,
        api_key,
        AppRuntimeTrainingQuizSubmissionRequest(
            conversationId=quiz_response.conversationId,
            quizMessageId=quiz_response.messageId,
            answers=[
                {"questionId": questions[0]["questionId"], "answer": questions[0]["correctAnswer"]},
                {"questionId": questions[1]["questionId"], "answer": "错误选项"},
            ],
        ),
    )

    assert response.score == 50
    assert response.passed is False
    assert len(response.results) == 2
    assert response.results[0].isCorrect is True
    assert response.results[1].isCorrect is False
    assert response.results[1].explanation

    message = db.execute(app_messages.select().where(app_messages.c.message_id == UUID(response.messageId))).mappings().one()
    assert message["qa_run_id"] == str(run_id)
    assert message["metadata"]["trainingResult"]["score"] == 50
    assert message["metadata"]["trainingResult"]["quizMessageId"] == quiz_response.messageId
