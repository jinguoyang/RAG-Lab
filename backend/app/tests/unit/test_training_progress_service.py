"""training_progress_service 单元测试。"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.training_progress import AnswerRecordDTO, ProgressDTO
from app.services.training_progress_service import (
    get_answer_records,
    get_progress,
    record_answer,
    update_progress,
)


# ---------------------------------------------------------------------------
# record_answer
# ---------------------------------------------------------------------------


class TestRecordAnswer:
    """record_answer 写入测试。"""

    @patch("app.services.training_progress_service.new_id", return_value="answer-001")
    @patch("app.services.training_progress_service.datetime")
    def test_record_answer_success(self, mock_dt, mock_new_id):
        """调用成功时应返回 answer_id 并写入数据库。"""
        mock_session = MagicMock()
        now = datetime(2025, 1, 1, tzinfo=UTC)
        mock_dt.now.return_value = now

        result = record_answer(
            mock_session,
            session_id="sess-001",
            app_id="app-001",
            end_user_id="user-001",
            question_id="q-001",
            question_type="single_choice",
            answer="A",
            score=100,
            is_correct=True,
            explanation="正确",
            metadata={"key": "value"},
        )

        assert result == "answer-001"
        mock_session.execute.assert_called_once()

    @patch("app.services.training_progress_service.new_id", return_value="answer-002")
    @patch("app.services.training_progress_service.datetime")
    def test_record_answer_optional_fields(self, mock_dt, mock_new_id):
        """可选字段为 None 时不应报错。"""
        mock_session = MagicMock()
        mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)

        result = record_answer(
            mock_session,
            session_id="sess-001",
            app_id="app-001",
            end_user_id="user-001",
            question_id="q-002",
            question_type="subjective",
            answer="长文本答案",
        )

        assert result == "answer-002"
        mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# update_progress
# ---------------------------------------------------------------------------


class TestUpdateProgress:
    """update_progress 创建和更新测试。"""

    @patch("app.services.training_progress_service.new_id", return_value="prog-001")
    @patch("app.services.training_progress_service.datetime")
    def test_create_new_progress(self, mock_dt, mock_new_id):
        """不存在记录时应创建新进度。"""
        mock_session = MagicMock()
        now = datetime(2025, 1, 1, tzinfo=UTC)
        mock_dt.now.return_value = now
        # get_progress 查询返回 None，表示不存在
        mock_session.execute.return_value.scalar.return_value = None

        update_progress(
            mock_session,
            session_id="sess-001",
            app_id="app-001",
            end_user_id="user-001",
            plan_id="plan-001",
            current_section_index=0,
            completed_sections=0,
            total_sections=5,
            last_score=None,
            status="in_progress",
        )

        # 两次 execute：一次 select 检查，一次 insert
        assert mock_session.execute.call_count == 2

    @patch("app.services.training_progress_service.new_id", return_value="prog-001")
    @patch("app.services.training_progress_service.datetime")
    def test_update_existing_progress(self, mock_dt, mock_new_id):
        """已存在记录时应更新。"""
        mock_session = MagicMock()
        now = datetime(2025, 1, 1, tzinfo=UTC)
        mock_dt.now.return_value = now
        # 模拟已存在
        mock_session.execute.return_value.scalar.return_value = "existing-prog-id"

        update_progress(
            mock_session,
            session_id="sess-001",
            app_id="app-001",
            end_user_id="user-001",
            plan_id="plan-001",
            current_section_index=2,
            completed_sections=2,
            total_sections=5,
            last_score=85,
            status="in_progress",
        )

        # 两次 execute：一次 select 检查，一次 update
        assert mock_session.execute.call_count == 2

    @patch("app.services.training_progress_service.new_id", return_value="prog-001")
    @patch("app.services.training_progress_service.datetime")
    def test_update_progress_completed(self, mock_dt, mock_new_id):
        """完成状态应正确传递。"""
        mock_session = MagicMock()
        mock_dt.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
        mock_session.execute.return_value.scalar.return_value = "existing-id"

        update_progress(
            mock_session,
            session_id="sess-001",
            app_id="app-001",
            end_user_id="user-001",
            current_section_index=5,
            completed_sections=5,
            total_sections=5,
            last_score=90,
            status="completed",
        )

        assert mock_session.execute.call_count == 2


# ---------------------------------------------------------------------------
# get_progress
# ---------------------------------------------------------------------------


class TestGetProgress:
    """get_progress 隔离和查询测试。"""

    def test_get_progress_found(self):
        """记录存在时应返回 ProgressDTO。"""
        mock_session = MagicMock()
        now = datetime(2025, 1, 1, tzinfo=UTC)
        mock_row = {
            "session_id": "sess-001",
            "app_id": "app-001",
            "end_user_id": "user-001",
            "current_section_index": 2,
            "completed_sections": 2,
            "total_sections": 5,
            "last_score": 85,
            "status": "in_progress",
            "updated_at": now,
        }
        mock_session.execute.return_value.mappings.return_value.first.return_value = mock_row

        result = get_progress(mock_session, "sess-001", "app-001", "user-001")

        assert result is not None
        assert result.sessionId == "sess-001"
        assert result.appId == "app-001"
        assert result.endUserId == "user-001"
        assert result.currentSectionIndex == 2
        assert result.completedSections == 2
        assert result.totalSections == 5
        assert result.lastScore == 85
        assert result.status == "in_progress"

    def test_get_progress_not_found(self):
        """记录不存在时应返回 None。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = None

        result = get_progress(mock_session, "sess-nonexistent", "app-001", "user-001")

        assert result is None

    def test_progress_isolated_by_session(self):
        """不同 session_id 应隔离查询。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = None

        result = get_progress(mock_session, "sess-other", "app-001", "user-001")

        assert result is None

    def test_progress_isolated_by_app(self):
        """不同 app_id 应隔离查询。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = None

        result = get_progress(mock_session, "sess-001", "app-other", "user-001")

        assert result is None

    def test_progress_isolated_by_user(self):
        """不同 end_user_id 应隔离查询。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = None

        result = get_progress(mock_session, "sess-001", "app-001", "user-other")

        assert result is None


# ---------------------------------------------------------------------------
# get_answer_records
# ---------------------------------------------------------------------------


class TestGetAnswerRecords:
    """get_answer_records 过滤测试。"""

    def test_get_answer_records_returns_list(self):
        """有记录时应返回 AnswerRecordDTO 列表。"""
        mock_session = MagicMock()
        now = datetime(2025, 1, 1, tzinfo=UTC)
        mock_rows = [
            {
                "answer_id": "ans-001",
                "session_id": "sess-001",
                "question_id": "q-001",
                "question_type": "single_choice",
                "answer": "A",
                "score": 100,
                "is_correct": True,
                "explanation": "正确",
                "created_at": now,
            },
            {
                "answer_id": "ans-002",
                "session_id": "sess-001",
                "question_id": "q-002",
                "question_type": "true_false",
                "answer": "true",
                "score": 0,
                "is_correct": False,
                "explanation": "不正确",
                "created_at": now,
            },
        ]
        mock_session.execute.return_value.mappings.return_value.all.return_value = mock_rows

        result = get_answer_records(mock_session, "sess-001", "app-001")

        assert len(result) == 2
        assert result[0].answerId == "ans-001"
        assert result[0].questionId == "q-001"
        assert result[0].score == 100
        assert result[0].isCorrect is True
        assert result[1].answerId == "ans-002"
        assert result[1].questionId == "q-002"
        assert result[1].score == 0
        assert result[1].isCorrect is False

    def test_get_answer_records_empty(self):
        """无记录时应返回空列表。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_answer_records(mock_session, "sess-empty", "app-001")

        assert result == []

    def test_get_answer_records_filtered_by_app(self):
        """应按 app_id 过滤。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_answer_records(mock_session, "sess-001", "app-other")

        assert result == []
