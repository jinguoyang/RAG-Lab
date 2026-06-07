"""ex-app 手动生成题目草稿测试。"""
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.schemas.training_question import TrainingQuestionDraftRequest
from app.services.training_question_service import create_question_drafts
from app.tables import metadata, training_questions


def test_manual_generation_allows_duplicate_document(monkeypatch):
    """手动生成对单个文档再次出题时，不执行自动生成去重规则。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    now = datetime.now(timezone.utc)
    session.execute(
        training_questions.insert().values(
            question_id="existing",
            plan_id="plan-001",
            app_id="app-001",
            question_type="single_choice",
            category="practice",
            content="已有题目",
            options=[],
            correct_answer="A",
            explanation="",
            rubric=None,
            evidence_chunk_ids=[],
            status="published",
            metadata={"documentId": "doc-001"},
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    captured = {}

    class FakeClient:
        def __init__(self, base_url, api_key):
            pass

        def create_question_drafts(self, **kwargs):
            captured.update(kwargs)
            return []

    monkeypatch.setenv("EXT_TRAINING_PLATFORM_API_KEY", "test-key")
    monkeypatch.setattr("app.services.platform_client.PlatformClient", FakeClient)

    try:
        result = create_question_drafts(
            session,
            "admin",
            TrainingQuestionDraftRequest(
                planId="plan-001",
                jobTitle="安全员",
                documentIds=["doc-001"],
            ),
        )

        assert result == []
        assert captured["document_ids"] == ["doc-001"]
    finally:
        session.close()
        metadata.drop_all(engine)
        engine.dispose()
