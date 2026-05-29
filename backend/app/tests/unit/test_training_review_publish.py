"""学习计划和题目审核发布服务单元测试。"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.training_agent_service import TrainingAgentConflictError, TrainingAgentNotFoundError
from app.services.training_plan_service import publish_plan, reject_plan
from app.services.training_question_service import publish_question, reject_question


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_plan_row(**overrides) -> dict:
    """构建模拟的 training_plans 行。"""
    now = datetime.now(UTC)
    defaults = {
        "plan_id": str(uuid4()),
        "app_id": str(uuid4()),
        "job_title": "安全工程师",
        "job_description": "负责安全管理",
        "status": "draft",
        "ability_groups": [{"name": "基础认知", "description": "desc"}],
        "documents": [{"documentId": "d1", "title": "Doc1", "relevance": 0.9, "abilityGroup": "基础认知", "difficulty": "basic"}],
        "evidence_chunk_ids": ["c1"],
        "recommend_reason": "推荐理由",
        "reading_order": ["d1"],
        "version": 1,
        "metadata": {"source": "test"},
        "created_at": now,
        "created_by": str(uuid4()),
        "updated_at": now,
        "updated_by": str(uuid4()),
    }
    defaults.update(overrides)
    return defaults


def _make_question_row(**overrides) -> dict:
    """构建模拟的 training_questions 行。"""
    now = datetime.now(UTC)
    defaults = {
        "question_id": str(uuid4()),
        "plan_id": str(uuid4()),
        "app_id": str(uuid4()),
        "question_type": "single_choice",
        "category": "practice",
        "content": "测试题目内容",
        "options": [{"label": "A", "text": "选项A"}, {"label": "B", "text": "选项B"}],
        "correct_answer": "A",
        "explanation": "解释",
        "rubric": None,
        "evidence_chunk_ids": ["c1"],
        "status": "draft",
        "metadata": {"source": "test"},
        "created_at": now,
        "created_by": str(uuid4()),
        "updated_at": now,
        "updated_by": str(uuid4()),
    }
    defaults.update(overrides)
    return defaults


def _mock_session_with_row(row: dict) -> MagicMock:
    """构建一个返回指定行的 mock session。"""
    mock_mapping = MagicMock()
    mock_mapping.first.return_value = row

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    session = MagicMock()
    session.execute.return_value = mock_result
    return session


def _mock_session_empty() -> MagicMock:
    """构建一个返回空结果的 mock session。"""
    mock_mapping = MagicMock()
    mock_mapping.first.return_value = None

    mock_result = MagicMock()
    mock_result.mappings.return_value = mock_mapping

    session = MagicMock()
    session.execute.return_value = mock_result
    return session


# ---------------------------------------------------------------------------
# publish_plan
# ---------------------------------------------------------------------------


class TestPublishPlan:
    def test_publish_plan_success(self):
        plan_id = str(uuid4())
        user_id = str(uuid4())
        row = _make_plan_row(plan_id=plan_id, status="draft")
        session = _mock_session_with_row(row)

        result = publish_plan(session, plan_id, user_id)

        assert result.status == "published"
        assert result.planId == plan_id
        session.commit.assert_called_once()

    def test_publish_plan_returns_correct_dto_fields(self):
        plan_id = str(uuid4())
        user_id = str(uuid4())
        row = _make_plan_row(plan_id=plan_id, status="draft")
        session = _mock_session_with_row(row)

        result = publish_plan(session, plan_id, user_id)

        assert result.jobTitle == "安全工程师"
        assert result.version == 1
        assert len(result.abilityGroups) == 1
        assert len(result.documents) == 1

    def test_publish_plan_not_found_raises(self):
        plan_id = str(uuid4())
        session = _mock_session_empty()

        with pytest.raises(TrainingAgentNotFoundError):
            publish_plan(session, plan_id, "user-1")

    def test_publish_plan_non_draft_raises_conflict(self):
        plan_id = str(uuid4())
        row = _make_plan_row(plan_id=plan_id, status="published")
        session = _mock_session_with_row(row)

        with pytest.raises(TrainingAgentConflictError):
            publish_plan(session, plan_id, "user-1")

    def test_publish_plan_rejected_status_raises_conflict(self):
        plan_id = str(uuid4())
        row = _make_plan_row(plan_id=plan_id, status="rejected")
        session = _mock_session_with_row(row)

        with pytest.raises(TrainingAgentConflictError):
            publish_plan(session, plan_id, "user-1")


# ---------------------------------------------------------------------------
# reject_plan
# ---------------------------------------------------------------------------


class TestRejectPlan:
    def test_reject_plan_success(self):
        plan_id = str(uuid4())
        user_id = str(uuid4())
        row = _make_plan_row(plan_id=plan_id, status="draft")
        session = _mock_session_with_row(row)

        result = reject_plan(session, plan_id, user_id)

        assert result.status == "rejected"
        assert result.planId == plan_id
        session.commit.assert_called_once()

    def test_reject_plan_non_draft_raises_conflict(self):
        plan_id = str(uuid4())
        row = _make_plan_row(plan_id=plan_id, status="rejected")
        session = _mock_session_with_row(row)

        with pytest.raises(TrainingAgentConflictError):
            reject_plan(session, plan_id, "user-1")


# ---------------------------------------------------------------------------
# publish_question
# ---------------------------------------------------------------------------


class TestPublishQuestion:
    def test_publish_question_success(self):
        question_id = str(uuid4())
        user_id = str(uuid4())
        row = _make_question_row(question_id=question_id, status="draft")
        session = _mock_session_with_row(row)

        result = publish_question(session, question_id, user_id)

        assert result.status == "published"
        assert result.questionId == question_id
        session.commit.assert_called_once()

    def test_publish_question_returns_correct_dto_fields(self):
        question_id = str(uuid4())
        user_id = str(uuid4())
        row = _make_question_row(question_id=question_id, status="draft")
        session = _mock_session_with_row(row)

        result = publish_question(session, question_id, user_id)

        assert result.questionType == "single_choice"
        assert result.content == "测试题目内容"
        assert len(result.options) == 2
        assert result.updatedAt is not None

    def test_publish_question_not_found_raises(self):
        question_id = str(uuid4())
        session = _mock_session_empty()

        with pytest.raises(TrainingAgentNotFoundError):
            publish_question(session, question_id, "user-1")

    def test_publish_question_non_draft_raises_conflict(self):
        question_id = str(uuid4())
        row = _make_question_row(question_id=question_id, status="published")
        session = _mock_session_with_row(row)

        with pytest.raises(TrainingAgentConflictError):
            publish_question(session, question_id, "user-1")


# ---------------------------------------------------------------------------
# reject_question
# ---------------------------------------------------------------------------


class TestRejectQuestion:
    def test_reject_question_success(self):
        question_id = str(uuid4())
        user_id = str(uuid4())
        row = _make_question_row(question_id=question_id, status="draft")
        session = _mock_session_with_row(row)

        result = reject_question(session, question_id, user_id)

        assert result.status == "rejected"
        assert result.questionId == question_id
        session.commit.assert_called_once()

    def test_reject_question_non_draft_raises_conflict(self):
        question_id = str(uuid4())
        row = _make_question_row(question_id=question_id, status="approved")
        session = _mock_session_with_row(row)

        with pytest.raises(TrainingAgentConflictError):
            reject_question(session, question_id, "user-1")
