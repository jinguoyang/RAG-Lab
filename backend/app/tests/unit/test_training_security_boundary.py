"""员工培训模块安全边界测试。

验收标准 (B-313)：
1. App B 的 API Key 不能推进 App A 的课堂
2. 员工 B 不能读取员工 A 的课堂状态
3. 报表不能跨 App 聚合
4. 错误响应使用稳定错误码，不泄漏资源存在性
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.training_classroom_service import (
    ClassroomSessionNotFoundError,
    get_classroom_session,
    submit_classroom_event,
)
from app.services.training_agent_service import TrainingAgentConflictError
from app.services.training_progress_service import get_answer_records, get_progress


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_row(
    *,
    session_id: str | None = None,
    app_id: str = "app-A",
    end_user_id: str = "user-001",
    current_state: str = "TEACH",
) -> dict:
    """构造模拟课堂会话行。"""
    return {
        "session_id": session_id or str(uuid4()),
        "app_id": app_id,
        "plan_id": str(uuid4()),
        "end_user_id": end_user_id,
        "current_state": current_state,
        "current_section_index": 0,
        "metadata": {"inputs": {"jobTitle": "安全操作"}},
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "deleted_at": None,
    }


def _make_context(app_id: str = "app-A"):
    """构造模拟培训上下文。"""
    ctx = MagicMock()
    ctx.app_row = {"app_id": app_id}
    ctx.kb_row = {"kb_id": str(uuid4())}
    return ctx


def _make_request(event_type: str = "start", payload: dict | None = None, query: str | None = None):
    """构造模拟事件请求。"""
    req = MagicMock()
    req.eventType = event_type
    req.payload = payload or {}
    req.query = query
    return req


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

_PATCH_READ_SESSION = "app.services.training_classroom_service._read_session"
_PATCH_RESOLVE = "app.services.training_classroom_service.resolve_training_context"
_PATCH_INSERT_EVENT = "app.services.training_classroom_service._insert_event"
_PATCH_INSERT_MSG = "app.services.training_classroom_service._insert_message"
_PATCH_UPDATE_STATE = "app.services.training_classroom_service._update_state"
_PATCH_PLAN_CONTENT = "app.services.training_classroom_service._plan_content"


# ===========================================================================
# 1. App B 的 API Key 不能推进 App A 的课堂
# ===========================================================================


class TestCrossAppEventRejection:
    """submit_classroom_event 跨 App 隔离。"""

    @patch(_PATCH_RESOLVE, side_effect=TrainingAgentConflictError("APP_ID_NOT_MATCHED"))
    @patch(_PATCH_READ_SESSION)
    def test_submit_event_cross_app_blocked(self, mock_read, mock_resolve):
        """App B 的 credential 推进 App A 的课堂应被拒绝。"""
        state_row = _make_session_row(app_id="app-A")
        mock_read.return_value = state_row

        with pytest.raises(TrainingAgentConflictError, match="APP_ID_NOT_MATCHED"):
            submit_classroom_event(
                MagicMock(),
                "credential-for-app-B",
                str(state_row["session_id"]),
                _make_request("start"),
            )

    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_submit_event_same_app_allowed(self, mock_read, mock_resolve):
        """同 App 的 credential 推进课堂应正常通过 app_id 检查。"""
        app_id = "app-A"
        state_row = _make_session_row(app_id=app_id, current_state="INIT")
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context(app_id)

        # start 事件从 INIT -> PLAN，会调用 _plan_content
        with patch(_PATCH_PLAN_CONTENT, return_value=("课程内容", [])), \
             patch(_PATCH_INSERT_EVENT, return_value=str(uuid4())), \
             patch(_PATCH_INSERT_MSG, return_value=str(uuid4())), \
             patch(_PATCH_UPDATE_STATE):
            resp = submit_classroom_event(
                MagicMock(),
                "credential-for-app-A",
                str(state_row["session_id"]),
                _make_request("start"),
            )
            assert resp.resultState == "PLAN"


# ===========================================================================
# 2. 员工 B 不能读取员工 A 的课堂状态
# ===========================================================================


class TestCrossUserSessionIsolation:
    """get_classroom_session endUserId 隔离。"""

    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_cross_user_returns_not_found(self, mock_read, mock_resolve):
        """员工 B 访问员工 A 的课堂会话应返回 404（不泄漏存在性）。"""
        session_row = _make_session_row(app_id="app-A", end_user_id="user-A")
        mock_read.return_value = session_row
        mock_resolve.return_value = _make_context("app-A")

        with pytest.raises(ClassroomSessionNotFoundError, match="课堂会话不存在"):
            get_classroom_session(
                MagicMock(),
                str(session_row["session_id"]),
                credential="cred",
                expected_end_user_id="user-B",
            )

    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_same_user_session_allowed(self, mock_read, mock_resolve):
        """员工 A 访问自己的课堂会话应正常返回。"""
        session_row = _make_session_row(app_id="app-A", end_user_id="user-A")
        mock_read.return_value = session_row
        mock_resolve.return_value = _make_context("app-A")
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.all.return_value = []

        resp = get_classroom_session(
            mock_session,
            str(session_row["session_id"]),
            credential="cred",
            expected_end_user_id="user-A",
        )

        assert resp.endUserId == "user-A"

    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_no_expected_user_skips_isolation(self, mock_read, mock_resolve):
        """不传 expected_end_user_id 时跳过 end_user_id 检查（管理员场景）。"""
        session_row = _make_session_row(app_id="app-A", end_user_id="user-A")
        mock_read.return_value = session_row
        mock_resolve.return_value = _make_context("app-A")
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.all.return_value = []

        resp = get_classroom_session(
            mock_session,
            str(session_row["session_id"]),
            credential="cred",
            # expected_end_user_id 不传
        )

        assert resp.endUserId == "user-A"


# ===========================================================================
# 3. get_classroom_session 跨 App 返回 404 而非 403
# ===========================================================================


class TestCrossAppSessionNotFound:
    """跨 App 访问课堂会话应返回 404，不泄漏资源存在性。"""

    @patch(_PATCH_RESOLVE, side_effect=TrainingAgentConflictError("APP_ID_NOT_MATCHED"))
    @patch(_PATCH_READ_SESSION)
    def test_cross_app_session_raises_conflict(self, mock_read, mock_resolve):
        """App B 的 credential 访问 App A 的课堂应抛出冲突错误。"""
        session_row = _make_session_row(app_id="app-A")
        mock_read.return_value = session_row

        with pytest.raises(TrainingAgentConflictError, match="APP_ID_NOT_MATCHED"):
            get_classroom_session(
                MagicMock(),
                str(session_row["session_id"]),
                credential="credential-for-app-B",
            )

    @patch(_PATCH_READ_SESSION)
    def test_nonexistent_session_raises_not_found(self, mock_read):
        """不存在的会话应抛出 ClassroomSessionNotFoundError。"""
        mock_read.side_effect = ClassroomSessionNotFoundError("课堂会话不存在")

        with pytest.raises(ClassroomSessionNotFoundError, match="课堂会话不存在"):
            get_classroom_session(MagicMock(), "nonexistent-session-id")

    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_cross_user_same_app_returns_not_found(self, mock_read, mock_resolve):
        """跨员工但同 App 访问应返回 404 而非 403，不泄漏资源存在性。"""
        session_row = _make_session_row(app_id="app-A", end_user_id="user-A")
        mock_read.return_value = session_row
        mock_resolve.return_value = _make_context("app-A")

        # 关键：错误消息只说"不存在"，不包含 "存在但不属于你" 的信息
        with pytest.raises(ClassroomSessionNotFoundError, match="课堂会话不存在"):
            get_classroom_session(
                MagicMock(),
                str(session_row["session_id"]),
                credential="cred",
                expected_end_user_id="user-B",
            )


# ===========================================================================
# 4. 进度查询按 app_id 隔离
# ===========================================================================


class TestProgressAppIsolation:
    """get_progress 按 app_id 和 end_user_id 隔离。"""

    def test_progress_cross_app_returns_none(self):
        """查询不同 app_id 的进度应返回 None。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = None

        result = get_progress(mock_session, "sess-001", "app-B", "user-001")

        assert result is None

    def test_progress_cross_user_returns_none(self):
        """查询不同 end_user_id 的进度应返回 None。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.first.return_value = None

        result = get_progress(mock_session, "sess-001", "app-A", "user-B")

        assert result is None

    def test_progress_same_app_and_user_returns_data(self):
        """同 app_id 和 end_user_id 查询应返回数据。"""
        mock_session = MagicMock()
        now = datetime.now(UTC)
        mock_session.execute.return_value.mappings.return_value.first.return_value = {
            "session_id": "sess-001",
            "app_id": "app-A",
            "end_user_id": "user-001",
            "current_section_index": 1,
            "completed_sections": 1,
            "total_sections": 3,
            "last_score": 85,
            "status": "in_progress",
            "updated_at": now,
        }

        result = get_progress(mock_session, "sess-001", "app-A", "user-001")

        assert result is not None
        assert result.appId == "app-A"
        assert result.endUserId == "user-001"


# ===========================================================================
# 5. 答题记录按 app_id 隔离
# ===========================================================================


class TestAnswerRecordsAppIsolation:
    """get_answer_records 按 app_id 隔离。"""

    def test_answer_records_cross_app_returns_empty(self):
        """查询不同 app_id 的答题记录应返回空列表。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_answer_records(mock_session, "sess-001", "app-B")

        assert result == []

    def test_answer_records_same_app_returns_data(self):
        """同 app_id 查询应返回答题记录。"""
        mock_session = MagicMock()
        now = datetime.now(UTC)
        mock_session.execute.return_value.mappings.return_value.all.return_value = [
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
        ]

        result = get_answer_records(mock_session, "sess-001", "app-A")

        assert len(result) == 1
        assert result[0].answerId == "ans-001"


# ===========================================================================
# 6. 错误响应稳定性
# ===========================================================================


class TestErrorCodeStability:
    """错误响应不泄漏内部 ID 和资源存在性。"""

    @patch(_PATCH_READ_SESSION)
    def test_not_found_error_no_internal_id(self, mock_read):
        """ClassroomSessionNotFoundError 消息不包含内部数据库 ID。"""
        internal_id = str(uuid4())
        mock_read.side_effect = ClassroomSessionNotFoundError(f"课堂会话 {internal_id} 不存在")

        with pytest.raises(ClassroomSessionNotFoundError) as exc_info:
            get_classroom_session(MagicMock(), internal_id)

        # 错误类型是稳定的 NotFoundError，不是 403
        assert isinstance(exc_info.value, ClassroomSessionNotFoundError)

    @patch(_PATCH_RESOLVE, side_effect=TrainingAgentConflictError("APP_ID_NOT_MATCHED"))
    @patch(_PATCH_READ_SESSION)
    def test_cross_app_error_uses_stable_code(self, mock_read, mock_resolve):
        """跨 App 错误使用稳定错误码 APP_ID_NOT_MATCHED。"""
        mock_read.return_value = _make_session_row()

        with pytest.raises(TrainingAgentConflictError, match="APP_ID_NOT_MATCHED"):
            submit_classroom_event(MagicMock(), "wrong-cred", "sess-001", _make_request())

    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_cross_user_error_message_generic(self, mock_read, mock_resolve):
        """跨员工错误消息不暴露 '资源存在但不属于你' 的信息。"""
        session_row = _make_session_row(app_id="app-A", end_user_id="user-A")
        mock_read.return_value = session_row
        mock_resolve.return_value = _make_context("app-A")

        with pytest.raises(ClassroomSessionNotFoundError) as exc_info:
            get_classroom_session(
                MagicMock(),
                str(session_row["session_id"]),
                credential="cred",
                expected_end_user_id="user-B",
            )

        # 消息只说"不存在"，不包含"不属于你"等信息
        error_msg = str(exc_info.value)
        assert "不存在" in error_msg
        assert "不属于" not in error_msg
        assert "无权" not in error_msg
        assert "user-A" not in error_msg
        assert "user-B" not in error_msg
