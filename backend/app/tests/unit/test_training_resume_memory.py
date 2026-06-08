"""课堂会话恢复功能单元测试：pendingActions、contextSummary、currentDocument。"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.training_classroom_service import (
    _get_context_summary,
    _get_current_document,
    _get_pending_actions,
)


# ---------------------------------------------------------------------------
# _get_pending_actions
# ---------------------------------------------------------------------------


class TestGetPendingActions:
    """_get_pending_actions 各状态测试。"""

    def test_init(self):
        row = {"metadata": None}
        result = _get_pending_actions("INIT", row)
        assert result == [{"label": "开始学习", "eventType": "start"}]

    def test_plan(self):
        row = {"metadata": None}
        result = _get_pending_actions("PLAN", row)
        assert result == [{"label": "开始学习", "eventType": "continue"}]

    def test_teach(self):
        row = {"metadata": None}
        result = _get_pending_actions("TEACH", row)
        assert len(result) == 2
        assert result[0]["eventType"] == "continue"
        assert result[1]["eventType"] == "query"

    def test_check_understand(self):
        row = {"metadata": None}
        result = _get_pending_actions("CHECK_UNDERSTAND", row)
        assert len(result) == 2
        assert result[0]["eventType"] == "continue"
        assert result[1]["eventType"] == "query"

    def test_quiz(self):
        row = {"metadata": None}
        result = _get_pending_actions("QUIZ", row)
        assert result == [{"label": "提交答案", "eventType": "submit_answer"}]

    def test_grade(self):
        row = {"metadata": None}
        result = _get_pending_actions("GRADE", row)
        assert result == [{"label": "查看复习建议", "eventType": "continue"}]

    def test_review_passed(self):
        row = {"metadata": {"lastPassed": True}}
        result = _get_pending_actions("REVIEW", row)
        assert result == [{"label": "完成复习", "eventType": "continue"}]

    def test_review_not_passed(self):
        row = {"metadata": {"lastPassed": False}}
        result = _get_pending_actions("REVIEW", row)
        assert len(result) == 2
        event_types = [a["eventType"] for a in result]
        assert "retry_teach" in event_types
        assert "retry_quiz" in event_types
        assert "continue" not in event_types

    def test_summary_not_last(self):
        row = {"metadata": None}
        result = _get_pending_actions("SUMMARY", row, is_last_section=False)
        assert result == [{"label": "下一节", "eventType": "next_section"}]

    def test_summary_last_section(self):
        row = {"metadata": None}
        result = _get_pending_actions("SUMMARY", row, is_last_section=True)
        assert result == [{"label": "完成课程", "eventType": "complete"}]

    def test_completed(self):
        row = {"metadata": None}
        result = _get_pending_actions("COMPLETED", row)
        assert result == []

    def test_off_topic(self):
        row = {"metadata": None}
        result = _get_pending_actions("OFF_TOPIC", row)
        assert result == [{"label": "回到课程", "eventType": "continue"}]

    def test_unknown_state(self):
        row = {"metadata": None}
        result = _get_pending_actions("UNKNOWN", row)
        assert result == []


# ---------------------------------------------------------------------------
# _get_context_summary
# ---------------------------------------------------------------------------


class TestGetContextSummary:
    """_get_context_summary 测试。"""

    def test_no_messages(self):
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []
        assert _get_context_summary(session, "s1") is None

    def test_only_user_messages(self):
        session = MagicMock()
        rows = [
            {"role": "user", "content": "问题1", "created_at": datetime.now(UTC)},
        ]
        session.execute.return_value.mappings.return_value.all.return_value = rows
        assert _get_context_summary(session, "s1") is None

    def test_assistant_messages_summarized(self):
        session = MagicMock()
        rows = [
            {"role": "assistant", "content": "A" * 200, "created_at": datetime.now(UTC)},
            {"role": "user", "content": "问题", "created_at": datetime.now(UTC)},
            {"role": "assistant", "content": "简短回答", "created_at": datetime.now(UTC)},
        ]
        session.execute.return_value.mappings.return_value.all.return_value = rows
        summary = _get_context_summary(session, "s1")
        assert summary is not None
        # 每条截取前 100 字
        assert "A" * 100 in summary
        assert "简短回答" in summary

    def test_truncates_to_100_chars(self):
        session = MagicMock()
        rows = [
            {"role": "assistant", "content": "X" * 150, "created_at": datetime.now(UTC)},
        ]
        session.execute.return_value.mappings.return_value.all.return_value = rows
        summary = _get_context_summary(session, "s1")
        # 取前 100 字
        assert len(summary) == 100


# ---------------------------------------------------------------------------
# _get_current_document
# ---------------------------------------------------------------------------


class TestGetCurrentDocument:
    """_get_current_document 测试。"""

    @patch("app.services.training_classroom_service.read_training_evidence")
    def test_returns_title(self, mock_evidence):
        mock_evidence.return_value = [
            {"document_id": "d1", "chunk_id": "c1", "heading": "安全规程", "section": None, "content": "text", "metadata": {"title": "安全操作规程"}},
        ]
        row = {"metadata": {"inputs": {"jobTitle": "安全"}}, "current_section_index": 0}
        result = _get_current_document(MagicMock(), row, "kb-1")
        assert result == "安全操作规程"

    @patch("app.services.training_classroom_service.read_training_evidence")
    def test_no_evidence(self, mock_evidence):
        mock_evidence.return_value = []
        row = {"metadata": {"inputs": {}}, "current_section_index": 0}
        assert _get_current_document(MagicMock(), row, "kb-1") is None

    def test_no_kb_id(self):
        row = {"metadata": {"inputs": {}}, "current_section_index": 0}
        assert _get_current_document(MagicMock(), row, None) is None

    @patch("app.services.training_classroom_service.read_training_evidence")
    def test_index_clamped(self, mock_evidence):
        mock_evidence.return_value = [
            {"document_id": "d1", "chunk_id": "c1", "heading": "H1", "section": None, "content": "", "metadata": {}},
        ]
        row = {"metadata": {"inputs": {}}, "current_section_index": 99}
        result = _get_current_document(MagicMock(), row, "kb-1")
        assert result == "H1"


# ---------------------------------------------------------------------------
# get_classroom_session metadata enrichment
# ---------------------------------------------------------------------------


class TestGetClassroomSessionMetadata:
    """get_classroom_session 返回的 metadata 包含恢复字段。"""

    @patch("app.services.training_classroom_service._resolve_kb_id")
    @patch("app.services.training_classroom_service._get_current_document")
    @patch("app.services.training_classroom_service._get_context_summary")
    def test_metadata_contains_resume_fields(self, mock_summary, mock_doc, mock_kb):
        session = MagicMock()
        session_id = str(uuid4())
        now = datetime.now(UTC)
        row = {
            "session_id": session_id,
            "app_id": "app-1",
            "plan_id": None,
            "end_user_id": "user-1",
            "current_state": "TEACH",
            "current_section_index": 0,
            "metadata": {"inputs": {"jobTitle": "安全"}},
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        session.execute.return_value.mappings.return_value.first.return_value = row
        session.execute.return_value.mappings.return_value.all.return_value = []
        mock_kb.return_value = "kb-1"
        mock_summary.return_value = "摘要内容"
        mock_doc.return_value = "安全操作规程"

        from app.services.training_classroom_service import get_classroom_session

        result = get_classroom_session(session, session_id)
        assert "pendingActions" in result.metadata
        assert "contextSummary" in result.metadata
        assert "currentDocument" in result.metadata
        assert "currentSectionIndex" in result.metadata
        assert result.metadata["contextSummary"] == "摘要内容"
        assert result.metadata["currentDocument"] == "安全操作规程"
        assert result.metadata["currentSectionIndex"] == 0

    @patch("app.services.training_classroom_service._resolve_kb_id")
    @patch("app.services.training_classroom_service._get_current_document")
    @patch("app.services.training_classroom_service._get_context_summary")
    def test_completed_pending_actions_empty(self, mock_summary, mock_doc, mock_kb):
        session = MagicMock()
        session_id = str(uuid4())
        now = datetime.now(UTC)
        row = {
            "session_id": session_id,
            "app_id": "app-1",
            "plan_id": None,
            "end_user_id": "user-1",
            "current_state": "COMPLETED",
            "current_section_index": 2,
            "metadata": {},
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        session.execute.return_value.mappings.return_value.first.return_value = row
        session.execute.return_value.mappings.return_value.all.return_value = []
        mock_kb.return_value = "kb-1"
        mock_summary.return_value = None
        mock_doc.return_value = None

        from app.services.training_classroom_service import get_classroom_session

        result = get_classroom_session(session, session_id)
        assert result.metadata["pendingActions"] == []
