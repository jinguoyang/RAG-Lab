"""课堂服务章节边界、错题复习和课程完成逻辑单元测试。"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.training_classroom_service import (
    ClassroomTransitionError,
    _count_sections,
    _get_passing_score,
    validate_classroom_transition,
)


# ---------------------------------------------------------------------------
# _get_passing_score
# ---------------------------------------------------------------------------


class TestGetPassingScore:
    """_get_passing_score 测试。"""

    def test_default_passing_score(self):
        row = {"metadata": None}
        assert _get_passing_score(row) == 80

    def test_custom_passing_score(self):
        row = {"metadata": {"inputs": {"scenarioConfig": {"passingScore": 70}}}}
        assert _get_passing_score(row) == 70

    def test_missing_scenario_config(self):
        row = {"metadata": {"inputs": {}}}
        assert _get_passing_score(row) == 80

    def test_missing_inputs(self):
        row = {"metadata": {}}
        assert _get_passing_score(row) == 80

    def test_non_dict_metadata(self):
        row = {"metadata": "invalid"}
        assert _get_passing_score(row) == 80


# ---------------------------------------------------------------------------
# _count_sections
# ---------------------------------------------------------------------------


class TestCountSections:
    """_count_sections 测试。"""

    @patch("app.services.training_classroom_service.read_training_evidence")
    def test_returns_evidence_count(self, mock_evidence):
        mock_evidence.return_value = [{"chunk_id": i} for i in range(3)]
        assert _count_sections(MagicMock(), "kb-1", "query") == 3

    @patch("app.services.training_classroom_service.read_training_evidence")
    def test_returns_zero_when_empty(self, mock_evidence):
        mock_evidence.return_value = []
        assert _count_sections(MagicMock(), "kb-1", "query") == 0


# ---------------------------------------------------------------------------
# validate_classroom_transition
# ---------------------------------------------------------------------------


class TestValidateClassroomTransition:
    """状态流转合法性测试。"""

    def test_grade_to_review_allowed(self):
        assert validate_classroom_transition("GRADE", "REVIEW") is True

    def test_grade_to_quiz_allowed(self):
        assert validate_classroom_transition("GRADE", "QUIZ") is True

    def test_review_to_teach_allowed(self):
        assert validate_classroom_transition("REVIEW", "TEACH") is True

    def test_review_to_quiz_allowed(self):
        assert validate_classroom_transition("REVIEW", "QUIZ") is True

    def test_summary_to_next_section_allowed(self):
        assert validate_classroom_transition("SUMMARY", "NEXT_SECTION") is True

    def test_summary_to_completed_allowed(self):
        assert validate_classroom_transition("SUMMARY", "COMPLETED") is True

    def test_completed_to_any_blocked(self):
        for state in ("INIT", "PLAN", "TEACH", "QUIZ", "GRADE", "REVIEW", "SUMMARY"):
            assert validate_classroom_transition("COMPLETED", state) is False


# ---------------------------------------------------------------------------
# submit_classroom_event 集成测试（mock 数据库）
# ---------------------------------------------------------------------------


def _make_state_row(
    current_state: str = "QUIZ",
    section_index: int = 0,
    metadata: dict | None = None,
) -> dict:
    """构造模拟课堂会话行。"""
    return {
        "session_id": str(uuid4()),
        "app_id": str(uuid4()),
        "current_state": current_state,
        "current_section_index": section_index,
        "end_user_id": "user-001",
        "metadata": metadata or {"inputs": {"jobTitle": "安全操作", "scenarioConfig": {"passingScore": 80}}},
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deleted_at": None,
    }


def _make_context():
    """构造模拟培训上下文。"""
    ctx = MagicMock()
    ctx.app_row = {"app_id": str(uuid4())}
    ctx.kb_row = {"kb_id": str(uuid4())}
    return ctx


def _make_request(event_type: str, payload: dict | None = None, query: str | None = None):
    """构造模拟事件请求。"""
    req = MagicMock()
    req.eventType = event_type
    req.payload = payload or {}
    req.query = query
    return req


# Patch targets
_PATCH_READ_SESSION = "app.services.training_classroom_service._read_session"
_PATCH_RESOLVE = "app.services.training_classroom_service.resolve_training_context"
_PATCH_EVIDENCE = "app.services.training_classroom_service.read_training_evidence"
_PATCH_INSERT_EVENT = "app.services.training_classroom_service._insert_event"
_PATCH_INSERT_MSG = "app.services.training_classroom_service._insert_message"
_PATCH_UPDATE_STATE = "app.services.training_classroom_service._update_state"
_PATCH_MERGE_META = "app.services.training_classroom_service._merge_session_metadata"
_PATCH_QUIZ_PAYLOAD = "app.services.training_classroom_service._quiz_payload"
_PATCH_GRADE = "app.services.training_classroom_service._grade_answer"


class TestGradePassAndFail:
    """测验通过/未通过后的 GRADE 行为。"""

    @patch(_PATCH_MERGE_META)
    @patch(_PATCH_GRADE, return_value=(100, "回答正确。"))
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_pass_shows_pass_message(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_grade, mock_merge
    ):
        """通过测验后显示达到通过线的消息。"""
        state_row = _make_state_row("QUIZ")
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("submit_answer", {"answer": "true", "questionId": "inline-true-false"}))

        assert "达到通过线" in resp.visibleContent
        assert resp.resultState == "GRADE"

    @patch(_PATCH_MERGE_META)
    @patch(_PATCH_GRADE, return_value=(0, "回答不正确，请回看本节材料。"))
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_fail_shows_fail_message(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_grade, mock_merge
    ):
        """未通过测验后显示未达到通过线的消息。"""
        state_row = _make_state_row("QUIZ")
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("submit_answer", {"answer": "false", "questionId": "inline-true-false"}))

        assert "未达到通过线" in resp.visibleContent
        assert resp.resultState == "GRADE"


class TestReviewAfterFail:
    """未通过测验后的 REVIEW 行为。"""

    @patch("app.services.training_classroom_service._current_evidence")
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_fail_review_shows_wrong_answer_and_retry_buttons(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence
    ):
        """未通过测验进入 REVIEW 时显示错题材料和重新学习/测验按钮。"""
        state_row = _make_state_row("GRADE", metadata={
            "inputs": {"jobTitle": "安全操作", "scenarioConfig": {"passingScore": 80}},
            "lastScore": 0,
            "lastPassed": False,
            "lastPassingScore": 80,
        })
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_evidence.return_value = (
            "安全操作材料摘要",
            [],
        )
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("continue"))

        assert resp.resultState == "REVIEW"
        assert "未通过" in resp.visibleContent
        # 应该有重新学习、重新测验、完成复习三个按钮
        buttons = resp.uiActions[0].data["buttons"]
        event_types = [b["eventType"] for b in buttons]
        assert "retry_teach" in event_types
        assert "retry_quiz" in event_types
        assert "continue" in event_types

    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_pass_review_shows_suggestions(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg
    ):
        """通过测验进入 REVIEW 时显示复习建议和完成复习按钮。"""
        state_row = _make_state_row("GRADE", metadata={
            "inputs": {"jobTitle": "安全操作", "scenarioConfig": {"passingScore": 80}},
            "lastScore": 100,
            "lastPassed": True,
            "lastPassingScore": 80,
        })
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("continue"))

        assert resp.resultState == "REVIEW"
        assert "复习建议" in resp.visibleContent
        buttons = resp.uiActions[0].data["buttons"]
        assert len(buttons) == 1
        assert buttons[0]["eventType"] == "continue"


class TestReviewRetryFlow:
    """REVIEW 中重新学习/重新测验的流转。"""

    @patch("app.services.training_classroom_service._current_evidence")
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_retry_teach_transitions_to_teach(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence
    ):
        """点击"重新学习"从 REVIEW 流转到 TEACH。"""
        state_row = _make_state_row("REVIEW")
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_evidence.return_value = ("学习材料", [])
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("retry_teach"))

        assert resp.resultState == "TEACH"
        assert "重新学习" in resp.visibleContent

    @patch(_PATCH_QUIZ_PAYLOAD, return_value=("测验内容", [], []))
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_retry_quiz_transitions_to_quiz(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_quiz
    ):
        """点击"重新测验"从 REVIEW 流转到 QUIZ。"""
        state_row = _make_state_row("REVIEW")
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("retry_quiz"))

        assert resp.resultState == "QUIZ"


class TestSummaryLastSection:
    """最后一节的 SUMMARY 行为。"""

    @patch(_PATCH_EVIDENCE, return_value=[{"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"}])
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_last_section_only_shows_complete_button(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence
    ):
        """最后一节的 SUMMARY 只显示"完成课程"按钮。"""
        state_row = _make_state_row("REVIEW", section_index=2, metadata={
            "inputs": {"jobTitle": "安全操作"},
            "lastPassed": True,
        })
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("continue"))

        assert resp.resultState == "SUMMARY"
        buttons = resp.uiActions[0].data["buttons"]
        event_types = [b["eventType"] for b in buttons]
        assert "complete" in event_types
        assert "next_section" not in event_types
        assert "所有章节已完成" in resp.visibleContent

    @patch(_PATCH_EVIDENCE, return_value=[{"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"}])
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_non_last_section_shows_next_and_complete(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence
    ):
        """非最后一节的 SUMMARY 显示"下一节"和"完成课程"按钮。"""
        state_row = _make_state_row("REVIEW", section_index=0, metadata={
            "inputs": {"jobTitle": "安全操作"},
            "lastPassed": True,
        })
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("continue"))

        assert resp.resultState == "SUMMARY"
        buttons = resp.uiActions[0].data["buttons"]
        event_types = [b["eventType"] for b in buttons]
        assert "next_section" in event_types
        assert "complete" in event_types


class TestNextSectionBoundary:
    """next_section 越界拦截测试。"""

    @patch(_PATCH_EVIDENCE, return_value=[{"chunk_id": "c1"}, {"chunk_id": "c2"}])
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_last_section_blocks_next_section(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence
    ):
        """最后一节点击"下一节"应抛出 ClassroomTransitionError。"""
        state_row = _make_state_row("SUMMARY", section_index=1)
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        with pytest.raises(ClassroomTransitionError, match="最后一节"):
            submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("next_section"))

    @patch("app.services.training_classroom_service._current_evidence")
    @patch(_PATCH_EVIDENCE, return_value=[{"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"}])
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_non_last_section_allows_next_section(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence, mock_current
    ):
        """非最后一节点击"下一节"应正常流转到 TEACH。"""
        state_row = _make_state_row("SUMMARY", section_index=0)
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_current.return_value = ("下一节学习材料", [])
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("next_section"))

        assert resp.resultState == "TEACH"


class TestCompleteBoundary:
    """complete 事件的章节边界拦截。"""

    @patch(_PATCH_EVIDENCE, return_value=[{"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"}])
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_premature_complete_blocked(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence
    ):
        """未完成所有章节时点击"完成课程"应抛出 ClassroomTransitionError。"""
        state_row = _make_state_row("SUMMARY", section_index=0)
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        with pytest.raises(ClassroomTransitionError, match="还有未完成的章节"):
            submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("complete"))

    @patch(_PATCH_EVIDENCE, return_value=[{"chunk_id": "c1"}, {"chunk_id": "c2"}])
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_last_section_complete_allowed(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence
    ):
        """最后一节点击"完成课程"应成功流转到 COMPLETED。"""
        state_row = _make_state_row("SUMMARY", section_index=1)
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("complete"))

        assert resp.resultState == "COMPLETED"


class TestReviewContainsCitation:
    """复行阶段包含错题解释和 Citation。"""

    @patch("app.services.training_classroom_service._current_evidence")
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_fail_review_includes_citations(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence
    ):
        """未通过测验进入 REVIEW 时应包含证据引用。"""
        from app.services.training_classroom_service import ClassroomCitationDTO

        citation = ClassroomCitationDTO(documentId="doc-1", chunkId="chunk-1", content="证据摘要", score=1.0)
        state_row = _make_state_row("GRADE", metadata={
            "inputs": {"jobTitle": "安全操作", "scenarioConfig": {"passingScore": 80}},
            "lastScore": 0,
            "lastPassed": False,
            "lastPassingScore": 80,
        })
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_evidence.return_value = ("安全操作材料摘要", [citation])
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("continue"))

        assert resp.resultState == "REVIEW"
        assert len(resp.citations) > 0
        assert resp.citations[0].documentId == "doc-1"
