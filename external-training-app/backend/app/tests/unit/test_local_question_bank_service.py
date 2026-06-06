"""ex-app 本地题库、异议和课后测验服务测试。"""
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.schemas.training_post_quiz import PostQuizStartRequest, PostQuizSubmitRequest
from app.schemas.training_question import (
    TrainingQuestionAppealRequest,
    TrainingQuestionAppealResolveRequest,
    TrainingQuestionReviewRequest,
)
from app.services.training_post_quiz_service import create_post_quiz, submit_post_quiz
from app.services.training_question_service import (
    count_questions_by_document,
    create_question_appeal,
    resolve_question_appeal,
    review_question,
)
from app.tables import metadata, training_classroom_sessions, training_questions


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


def _insert_question(
    session,
    question_id: str,
    question_type: str,
    answer: str | None = None,
    status: str = "draft",
    plan_id: str = "plan-001",
):
    """插入一条本地题库记录。"""
    now = datetime.now(timezone.utc)
    session.execute(
        training_questions.insert().values(
            question_id=question_id,
            plan_id=plan_id,
            app_id="app-001",
            question_type=question_type,
            category="quiz",
            content=f"{question_id} 题干",
            options=[{"label": "A", "text": "正确"}, {"label": "B", "text": "错误"}] if question_type != "subjective" else [],
            correct_answer=answer,
            explanation="解析",
            rubric={"totalScore": 5, "criteria": [{"name": "识别风险", "score": 5}]} if question_type == "subjective" else None,
            evidence_chunk_ids=[],
            status=status,
            metadata={"documentId": "doc-001"},
            created_at=now,
            updated_at=now,
        )
    )


def test_review_and_appeal_are_local():
    """题目审核和异议处理只更新 ex-app 本地表。"""
    engine, session = _session()
    try:
        _insert_question(session, "q-001", "single_choice", "A")
        session.commit()

        result = review_question(session, "admin", "q-001", TrainingQuestionReviewRequest(decision="approved").decision)
        assert result == {"questionId": "q-001", "status": "approved"}

        appeal = create_question_appeal(
            session,
            "q-001",
            TrainingQuestionAppealRequest(endUserId="u1", reason="答案有争议"),
        )
        assert appeal["status"] == "open"

        resolved = resolve_question_appeal(
            session,
            "admin",
            appeal["appealId"],
            TrainingQuestionAppealResolveRequest(status="resolved", resolution="已修正解析"),
        )
        assert resolved["status"] == "resolved"
        assert resolved["resolution"] == "已修正解析"
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_post_quiz_reuses_published_document_questions_from_other_plan(monkeypatch):
    """题目按文档复用，当前计划没有题目时也可使用其他计划同文档已发布题目。"""
    engine, session = _session()
    try:
        now = datetime.now(timezone.utc)
        session.execute(
            training_classroom_sessions.insert().values(
                session_id="session-001",
                app_id="app-001",
                plan_id="plan-001",
                end_user_id="u1",
                current_state="COMPLETED",
                current_section_index=0,
                metadata={},
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        _insert_question(session, "q-choice-1", "single_choice", "A", "published", plan_id="other-plan")
        session.commit()

        quiz = create_post_quiz(
            session,
            PostQuizStartRequest(sessionId="session-001", endUserId="u1", documentId="doc-001", planId="plan-001", count=1),
        )
        counts = count_questions_by_document(session, "plan-001")

        assert quiz["questions"][0]["questionId"] == "q-choice-1"
        assert counts["doc-001"] == 1
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()


def test_post_quiz_uses_local_published_questions(monkeypatch):
    """课后测验从 ex-app 本地 published 题库抽题，主观题才调用平台评分。"""
    engine, session = _session()
    try:
        now = datetime.now(timezone.utc)
        session.execute(
            training_classroom_sessions.insert().values(
                session_id="session-001",
                app_id="app-001",
                plan_id="plan-001",
                end_user_id="u1",
                current_state="COMPLETED",
                current_section_index=0,
                metadata={},
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        _insert_question(session, "q-choice-1", "single_choice", "A", "published")
        _insert_question(session, "q-choice-2", "single_choice", "A", "published")
        _insert_question(session, "q-tf-1", "true_false", "true", "published")
        _insert_question(session, "q-tf-2", "true_false", "true", "published")
        _insert_question(session, "q-sub-1", "subjective", None, "published")
        session.commit()

        class FakeClient:
            def grade_subjective_answer(self, payload):
                assert "questionId" not in payload
                return {"score": 5, "passed": True, "reason": "ok"}

        monkeypatch.setattr("app.services.training_post_quiz_service._platform_client", lambda: FakeClient())

        quiz = create_post_quiz(
            session,
            PostQuizStartRequest(sessionId="session-001", endUserId="u1", documentId="doc-001", planId="plan-001", count=5),
        )
        assert len(quiz["questions"]) == 5
        assert all("correctAnswer" not in item for item in quiz["questions"])

        submission = submit_post_quiz(
            session,
            quiz["quizId"],
            PostQuizSubmitRequest(
                endUserId="u1",
                answers=[
                    {"questionId": "q-choice-1", "answer": "A"},
                    {"questionId": "q-choice-2", "answer": "A"},
                    {"questionId": "q-tf-1", "answer": "true"},
                    {"questionId": "q-tf-2", "answer": "true"},
                    {"questionId": "q-sub-1", "answer": "按流程识别风险并上报。"},
                ],
            ),
        )
        assert submission["passed"] is True
        assert submission["score"] == 25
        session_row = session.execute(training_classroom_sessions.select()).mappings().one()
        assert session_row["metadata"]["completedDocumentIds"] == ["doc-001"]
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()
