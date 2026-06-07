"""学习计划本地保存和出题触发服务测试。"""
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.schemas.training_plan import TrainingPlanSaveRequest
from app.services.training_plan_service import generate_questions_for_plan, get_plan, save_plan
from app.tables import metadata, training_plans, training_post_quizzes, training_questions


def _session():
    """创建共享内存数据库会话。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    return engine, session


def test_save_plan_inserts_final_plan_without_existing_draft():
    """最终保存计划时允许本地不存在草稿，只落库 saved 计划并回显员工绑定。"""
    engine, session = _session()
    try:
        request = TrainingPlanSaveRequest(
            planName="安全员入职计划",
            appId="app-001",
            jobTitle="安全员",
            jobDescription="负责现场风险识别",
            abilityGroups=[{"name": "基础认知"}],
            documents=[{"documentId": "doc-001", "title": "安全手册", "difficulty": "初级", "category": "安全"}],
            evidenceChunkIds=["chunk-001"],
            recommendReason="覆盖基础安全要求",
            readingOrder=["doc-001"],
            employeeIds=["emp-001", "emp-002"],
            version=1,
        )

        result = save_plan(session, "admin", "plan-001", request)
        plan = get_plan(session, "plan-001")

        assert result == {"planId": "plan-001", "status": "saved"}
        assert plan["status"] == "saved"
        assert plan["employeeIds"] == ["emp-001", "emp-002"]
        assert plan["documents"][0]["documentId"] == "doc-001"
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_get_plan_keeps_document_passed_after_later_failed_retry():
    """文档任意一次课后测验通过后，后续重考失败仍保持通过状态。"""
    engine, session = _session()
    try:
        request = TrainingPlanSaveRequest(
            planName="安全员入职计划",
            appId="app-001",
            jobTitle="安全员",
            documents=[{"documentId": "doc-001", "title": "安全手册"}],
            readingOrder=["doc-001"],
        )
        save_plan(session, "admin", "plan-001", request)
        now = datetime.now(timezone.utc)
        session.execute(
            training_post_quizzes.insert(),
            [
                {
                    "quiz_id": "quiz-passed",
                    "session_id": "session-001",
                    "plan_id": "plan-001",
                    "app_id": "app-001",
                    "end_user_id": "demo-user",
                    "document_id": "doc-001",
                    "questions": [],
                    "answers": [],
                    "results": [],
                    "score": 20,
                    "passed": True,
                    "status": "submitted",
                    "created_at": now,
                    "submitted_at": now,
                    "updated_at": now,
                },
                {
                    "quiz_id": "quiz-failed-retry",
                    "session_id": "session-002",
                    "plan_id": "plan-001",
                    "app_id": "app-001",
                    "end_user_id": "demo-user",
                    "document_id": "doc-001",
                    "questions": [],
                    "answers": [],
                    "results": [],
                    "score": 15,
                    "passed": False,
                    "status": "submitted",
                    "created_at": now,
                    "submitted_at": now,
                    "updated_at": now,
                },
            ],
        )
        session.commit()

        plan = get_plan(session, "plan-001")

        assert plan["passedDocuments"] == ["doc-001"]
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_generate_questions_skips_document_generated_in_other_plan(monkeypatch):
    """同一文档已有草稿题目时，后台自动出题不重复调用平台。"""
    engine, session = _session()
    try:
        now = datetime.now(timezone.utc)
        session.execute(
            training_plans.insert().values(
                plan_id="plan-001",
                app_id="app-001",
                job_title="安全员",
                job_description="负责现场风险识别",
                status="saved",
                ability_groups=[],
                documents=[{"documentId": "doc-001", "title": "安全手册"}],
                evidence_chunk_ids=[],
                recommend_reason="",
                reading_order=["doc-001"],
                version=1,
                metadata={"planName": "安全员入职计划", "employeeIds": []},
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            training_questions.insert().values(
                question_id="question-existing",
                plan_id="other-plan",
                app_id="app-001",
                question_type="single_choice",
                category="practice",
                content="已有题目",
                options=[],
                correct_answer="A",
                explanation="",
                rubric=None,
                evidence_chunk_ids=[],
                status="draft",
                metadata={"documentId": "doc-001"},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

        calls = []

        class FakeClient:
            def __init__(self, base_url, api_key):
                pass

            def create_question_drafts(self, **kwargs):
                calls.append(kwargs)
                return []

        class SessionFactory:
            def __call__(self):
                return session

        monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
        monkeypatch.setattr("app.core.database.SessionLocal", SessionFactory())
        monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)

        generate_questions_for_plan("plan-001")

        assert calls == []
    finally:
        if session.is_active:
            session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_generate_questions_does_not_treat_legacy_approved_as_duplicate(monkeypatch):
    """自动生成只以 draft/published 去重，旧 approved 状态不阻止生成。"""
    engine, session = _session()
    try:
        now = datetime.now(timezone.utc)
        session.execute(
            training_plans.insert().values(
                plan_id="plan-001",
                app_id="app-001",
                job_title="安全员",
                job_description="负责现场风险识别",
                status="saved",
                ability_groups=[],
                documents=[{"documentId": "doc-001", "title": "安全手册"}],
                evidence_chunk_ids=[],
                recommend_reason="",
                reading_order=["doc-001"],
                version=1,
                metadata={"planName": "安全员入职计划", "employeeIds": []},
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            training_questions.insert().values(
                question_id="question-approved",
                plan_id="other-plan",
                app_id="app-001",
                question_type="single_choice",
                category="practice",
                content="旧状态题目",
                options=[],
                correct_answer="A",
                explanation="",
                rubric=None,
                evidence_chunk_ids=[],
                status="approved",
                metadata={"documentId": "doc-001"},
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        calls = []

        class FakeClient:
            def __init__(self, base_url, api_key):
                pass

            def create_question_drafts(self, **kwargs):
                calls.append(kwargs)
                return []

        class SessionFactory:
            def __call__(self):
                return session

        monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
        monkeypatch.setattr("app.core.database.SessionLocal", SessionFactory())
        monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)

        generate_questions_for_plan("plan-001")

        assert len(calls) == 1
        assert calls[0]["document_ids"] == ["doc-001"]
    finally:
        if session.is_active:
            session.close()
        metadata.drop_all(engine)
        engine.dispose()
