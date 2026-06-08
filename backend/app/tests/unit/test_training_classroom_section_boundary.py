"""课堂服务章节边界、错题复习和课程完成逻辑单元测试。"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.training_classroom import ClassroomUiActionDTO
from app.services.training_classroom_service import (
    ClassroomTransitionError,
    _answer_query_with_agent,
    _count_sections,
    _current_evidence,
    _get_passing_score,
    _is_low_value_teaching_evidence,
    _passed_section_summary,
    _plan_content,
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

    def test_uses_frozen_course_snapshot_sections(self):
        """存在冻结课程快照时，章节总数应来自 sections 而不是文档或 Chunk 数。"""
        session = MagicMock()
        session.execute.return_value.mappings.return_value.first.return_value = {
            "metadata": {
                "inputs": {
                    "courseSnapshot": {
                        "sections": [
                            {"sectionId": "s1", "title": "目标一", "sourceDocumentIds": ["d1"]},
                            {"sectionId": "s2", "title": "目标二", "sourceDocumentIds": ["d2"]},
                        ]
                    }
                }
            }
        }

        assert _count_sections(session, "kb-1", "安全员", session_id="session-1") == 2

    @patch("app.services.training_classroom_service.read_training_evidence")
    def test_returns_evidence_count(self, mock_evidence):
        mock_evidence.return_value = [{"chunk_id": i} for i in range(3)]
        assert _count_sections(MagicMock(), "kb-1", "query") == 3

    @patch("app.services.training_classroom_service.read_training_evidence")
    def test_returns_zero_when_empty(self, mock_evidence):
        mock_evidence.return_value = []
        assert _count_sections(MagicMock(), "kb-1", "query") == 0


class TestClassroomQuery:
    """新课程追问应直接使用当前章节讲稿，避免回退到 Chunk 检索式问答。"""

    @patch("app.services.training_classroom_service.call_llm")
    @patch("app.services.training_classroom_service._read_learning_plan")
    @patch("app.services.training_classroom_service._recent_context_messages", return_value=[])
    @patch("app.services.app_runtime_service.chat_with_app_runtime")
    def test_uses_current_section_script_when_runtime_reports_no_evidence(
        self,
        mock_runtime,
        _mock_history,
        mock_plan,
        mock_llm,
    ):
        mock_runtime.return_value = MagicMock(
            answer="当前用户没有可用于回答的授权证据。",
            citations=[],
        )
        mock_plan.return_value = {
            "metadata": {
                "sections": [
                    {
                        "sectionId": "section-1",
                        "title": "评审与处置",
                        "learningObjective": "理解跨部门评审",
                        "sourceDocumentIds": ["document-1"],
                        "teachingScript": {
                            "opening": "发现呆滞物料后怎么办？",
                            "explanation": "处置需要仓库、质量、财务和责任部门共同评审。",
                            "scenario": "高价值配件需比较退换、改造和出售方案。",
                            "interactionQuestions": ["为什么仓库不能单独决定？"],
                            "summary": "评审、审批、执行和归档缺一不可。",
                        },
                    }
                ]
            }
        }
        mock_llm.return_value = "仓库不能单独决定，因为报废同时涉及品质、资产和账务责任。"
        state_row = {
            "session_id": str(uuid4()),
            "app_id": str(uuid4()),
            "end_user_id": "employee-1",
            "current_state": "TEACH",
            "current_section_index": 0,
            "metadata": {},
        }

        answer, citations = _answer_query_with_agent(
            MagicMock(),
            "credential",
            state_row,
            "kb-1",
            "为什么不能由仓库直接决定报废？",
        )

        assert "品质、资产和账务责任" in answer
        assert "授权证据" not in answer
        assert citations == []
        mock_runtime.assert_not_called()
        assert "处置需要仓库、质量、财务和责任部门共同评审" in mock_llm.call_args.args[0][1]["content"]


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


class _FakeScalarResult:
    """模拟 SQLAlchemy 标量结果，用于不触库测试。"""

    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class _FakeMappingResult:
    """模拟 SQLAlchemy mappings().first() 链式结果。"""

    def __init__(self, value):
        self.value = value

    def mappings(self):
        return self

    def first(self):
        return self.value

    def all(self):
        if isinstance(self.value, list):
            return self.value
        return [] if self.value is None else [self.value]


class _PlanSession:
    """按调用顺序返回计划行和 metadata，避免单元测试依赖真实数据库。"""

    def __init__(self, plan_row: dict):
        self.plan_row = plan_row

    def execute(self, *_args, **_kwargs):
        return _FakeMappingResult(self.plan_row)


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

    @patch(_PATCH_MERGE_META)
    @patch(_PATCH_GRADE, return_value=(0, "未说明异常后的上报动作。"))
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_fail_feedback_targets_current_checkpoint_criteria(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_grade, mock_merge
    ):
        """未通过反馈应明确指出当前小节需要补强的验收标准。"""
        state_row = _make_state_row("QUIZ", metadata={
            "inputs": {
                "scenarioConfig": {"passingScore": 80},
                "courseSnapshot": {
                    "sections": [{
                        "sectionId": "section-b",
                        "title": "异常停机",
                        "checkpointCriteria": ["说明停机动作", "说明上报要求"],
                        "sourceDocumentIds": ["doc-b"],
                    }]
                },
            }
        })
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(
            MagicMock(),
            "cred",
            str(state_row["session_id"]),
            _make_request("submit_answer", {"answer": "立即停机", "questionId": "question-b"}),
        )

        assert "需要补强的验收标准" in resp.visibleContent
        assert "说明上报要求" in resp.visibleContent
        saved = mock_merge.call_args.args[2]
        assert saved["lastSectionId"] == "section-b"
        assert saved["lastCheckpointCriteria"] == ["说明停机动作", "说明上报要求"]


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
        # 未通过时只能重新学习或重新测验，不能直接完成复习后推进。
        buttons = resp.uiActions[0].data["buttons"]
        event_types = [b["eventType"] for b in buttons]
        assert "retry_teach" in event_types
        assert "retry_quiz" in event_types
        assert "continue" not in event_types

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

    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_failed_review_cannot_continue_to_summary(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg
    ):
        """未通过测验时，即使伪造 continue 事件也不能推进到 SUMMARY。"""
        state_row = _make_state_row("REVIEW", metadata={"lastPassed": False})
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()
        mock_session = MagicMock()

        from app.services.training_classroom_service import submit_classroom_event

        with pytest.raises(ClassroomTransitionError, match="尚未通过"):
            submit_classroom_event(mock_session, "cred", str(state_row["session_id"]), _make_request("continue"))

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

    @patch(
        _PATCH_QUIZ_PAYLOAD,
        return_value=("测验内容", [ClassroomUiActionDTO(actionType="true_false", data={"questionId": "question-001"})], []),
    )
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
    def test_non_last_section_only_shows_next(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_evidence
    ):
        """非最后一节的 SUMMARY 只显示"下一节"按钮。"""
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
        assert "complete" not in event_types

    @patch("app.services.training_classroom_service._count_sections", return_value=2)
    @patch(_PATCH_MERGE_META)
    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_passed_review_marks_current_section_completed(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg, mock_merge, _mock_count
    ):
        """通过 Checkpoint 后进入 SUMMARY 时记录当前小节完成。"""
        state_row = _make_state_row("REVIEW", section_index=0, metadata={
            "inputs": {
                "courseSnapshot": {
                    "sections": [
                        {"sectionId": "section-a", "title": "启动检查", "sourceDocumentIds": ["doc-a"]},
                        {"sectionId": "section-b", "title": "异常停机", "sourceDocumentIds": ["doc-b"]},
                    ]
                }
            },
            "lastPassed": True,
            "lastScore": 100,
        })
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()

        from app.services.training_classroom_service import submit_classroom_event

        resp = submit_classroom_event(MagicMock(), "cred", str(state_row["session_id"]), _make_request("continue"))

        assert resp.resultState == "SUMMARY"
        assert resp.progressUpdate.completedSections == 1
        assert mock_merge.call_args.args[2]["completedSectionIds"] == ["section-a"]


class TestQuizRequiresPreparedQuestion:
    """随堂 Checkpoint 由 LLM 根据当前小节讲稿现场出题。"""

    @patch("app.services.training_classroom_service._merge_session_metadata")
    @patch("app.services.training_classroom_service.begin_app_llm_invocation", side_effect=Exception("skip audit"))
    @patch("app.services.training_classroom_service.call_llm")
    @patch("app.services.training_classroom_service._render_teaching_script", return_value="教学内容：安全操作要点")
    def test_quiz_payload_generates_question_via_llm(self, _mock_script, mock_llm, _mock_begin, _mock_merge):
        """LLM 出题成功时返回 single_choice 动作。"""
        import json

        from app.services.training_classroom_service import _quiz_payload

        mock_llm.return_value = json.dumps({
            "stem": "以下哪项是安全操作的核心要求？",
            "options": [
                {"label": "A", "text": "佩戴防护装备"},
                {"label": "B", "text": "忽略警示标识"},
                {"label": "C", "text": "单独作业"},
                {"label": "D", "text": "口头汇报"},
            ],
            "correctAnswer": "A",
            "explanation": "安全操作要求必须佩戴防护装备。",
        })
        state_row = _make_state_row("CHECK_UNDERSTAND", metadata={
            "inputs": {
                "jobTitle": "安全操作",
                "courseSnapshot": {
                    "sections": [{
                        "sectionId": "section-a",
                        "title": "安全操作要点",
                        "checkpointCriteria": ["掌握防护要求"],
                        "sourceDocumentIds": ["doc-a"],
                        "evidenceChunkIds": ["chunk-a"],
                    }]
                }
            }
        })
        session = MagicMock()

        content, actions, _citations = _quiz_payload(session, state_row, "kb-001", "sess-001")

        assert "安全操作" in content
        assert len(actions) == 1
        assert actions[0].actionType == "single_choice"
        assert actions[0].data["questionId"] == "llm-quiz-section-a"
        assert actions[0].data["sectionId"] == "section-a"
        assert len(actions[0].data["options"]) == 4
        _mock_merge.assert_called_once()

    @patch("app.services.training_classroom_service._merge_session_metadata")
    @patch("app.services.training_classroom_service.begin_app_llm_invocation", side_effect=Exception("skip audit"))
    @patch("app.services.training_classroom_service.call_llm")
    @patch("app.services.training_classroom_service._render_teaching_script", return_value="教学内容")
    def test_quiz_payload_normalizes_text_answer_to_label(self, _mock_script, mock_llm, _mock_begin, mock_merge):
        """LLM 返回完整文本作为 correctAnswer 时，应自动标准化为标签字母。"""
        import json

        from app.services.training_classroom_service import _quiz_payload

        mock_llm.return_value = json.dumps({
            "stem": "以下哪项是安全操作的核心要求？",
            "options": [
                {"label": "A", "text": "佩戴防护装备"},
                {"label": "B", "text": "忽略警示标识"},
                {"label": "C", "text": "单独作业"},
                {"label": "D", "text": "口头汇报"},
            ],
            "correctAnswer": "佩戴防护装备",
            "explanation": "安全操作要求必须佩戴防护装备。",
        })
        state_row = _make_state_row("CHECK_UNDERSTAND")
        session = MagicMock()

        _quiz_payload(session, state_row, "kb-001", "sess-001")

        saved_meta = mock_merge.call_args[0][2]
        assert saved_meta["current_llm_quiz"]["correctAnswer"] == "A"

    @patch("app.services.training_classroom_service._merge_session_metadata")
    @patch("app.services.training_classroom_service.begin_app_llm_invocation", side_effect=Exception("skip audit"))
    @patch("app.services.training_classroom_service.call_llm", side_effect=Exception("LLM 不可用"))
    @patch("app.services.training_classroom_service._render_teaching_script", return_value=None)
    def test_quiz_payload_fallback_when_llm_fails(self, _mock_script, _mock_llm, _mock_begin, _mock_merge):
        """LLM 失败时回退为判断题，仍返回可答题的动作。"""
        from app.services.training_classroom_service import _quiz_payload

        state_row = _make_state_row("CHECK_UNDERSTAND")
        session = MagicMock()

        content, actions, _citations = _quiz_payload(session, state_row, "kb-001", "sess-001")

        assert len(actions) == 1
        assert actions[0].actionType == "true_false"
        assert actions[0].data["questionId"].startswith("llm-quiz-")
        _mock_merge.assert_called_once()

    def test_grade_llm_quiz_correct_answer(self):
        """LLM 出题的正确答案评分应返回满分。"""
        from app.services.training_classroom_service import _grade_answer

        state_row = _make_state_row("QUIZ", metadata={
            "current_llm_quiz": {
                "questionId": "llm-quiz-section-a",
                "correctAnswer": "A",
                "explanation": "安全操作要求佩戴防护装备。",
            },
        })
        session = MagicMock()

        score, explanation = _grade_answer(session, state_row, {"questionId": "llm-quiz-section-a", "answer": "A"})

        assert score == 100
        assert "正确" in explanation

    def test_grade_llm_quiz_wrong_answer(self):
        """LLM 出题的错误答案评分应返回 0 分和解析。"""
        from app.services.training_classroom_service import _grade_answer

        state_row = _make_state_row("QUIZ", metadata={
            "current_llm_quiz": {
                "questionId": "llm-quiz-section-a",
                "correctAnswer": "A",
                "explanation": "安全操作要求佩戴防护装备。",
            },
        })
        session = MagicMock()

        score, explanation = _grade_answer(session, state_row, {"questionId": "llm-quiz-section-a", "answer": "B"})

        assert score == 0
        assert "不正确" in explanation
        assert "佩戴防护装备" in explanation

    def test_grade_rejects_question_from_another_section(self):
        """即使伪造提交其他小节题目，服务端评分也必须拒绝。"""
        state_row = _make_state_row("QUIZ", metadata={
            "inputs": {
                "courseSnapshot": {
                    "sections": [{
                        "sectionId": "section-b",
                        "title": "异常停机",
                        "sourceDocumentIds": ["doc-b"],
                        "evidenceChunkIds": ["chunk-b"],
                    }]
                }
            }
        })
        session = MagicMock()
        session.execute.return_value.mappings.return_value.first.return_value = {
            "question_id": "question-a",
            "question_type": "true_false",
            "correct_answer": "true",
            "explanation": "第一节反馈",
            "evidence_chunk_ids": ["chunk-a"],
            "metadata": {"documentId": "doc-a"},
        }

        from app.services.training_classroom_service import ClassroomEventError, _grade_answer

        with pytest.raises(ClassroomEventError, match="不属于当前小节"):
            _grade_answer(session, state_row, {"questionId": "question-a", "answer": "true"})


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

    @patch(_PATCH_INSERT_MSG, return_value=str(uuid4()))
    @patch(_PATCH_INSERT_EVENT, return_value=str(uuid4()))
    @patch(_PATCH_UPDATE_STATE)
    @patch(_PATCH_RESOLVE)
    @patch(_PATCH_READ_SESSION)
    def test_structured_course_requires_all_section_completion_ids(
        self, mock_read, mock_resolve, mock_update, mock_event, mock_msg
    ):
        """结构化课程即使位于末节，也必须确认所有小节均已通过 Checkpoint。"""
        state_row = _make_state_row("SUMMARY", section_index=1, metadata={
            "inputs": {
                "courseSnapshot": {
                    "sections": [
                        {"sectionId": "section-a", "title": "启动检查", "sourceDocumentIds": ["doc-a"]},
                        {"sectionId": "section-b", "title": "异常停机", "sourceDocumentIds": ["doc-b"]},
                    ]
                }
            },
            "lastPassed": True,
            "completedSectionIds": ["section-b"],
        })
        mock_read.return_value = state_row
        mock_resolve.return_value = _make_context()

        from app.services.training_classroom_service import submit_classroom_event

        with pytest.raises(ClassroomTransitionError, match="尚未通过 Checkpoint"):
            submit_classroom_event(MagicMock(), "cred", str(state_row["session_id"]), _make_request("complete"))


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


class TestClassroomUsesLearningPlan:
    """课堂内容应优先绑定已生成的学习计划。"""

    @pytest.mark.parametrize(
        ("heading", "content"),
        [
            ("封面", "企业标准 2026 年 6 月发布"),
            ("目录", "第一章 概述 第二章 操作要求"),
            ("版本记录", "V1.0 初次发布"),
            ("附录 A", ""),
            (
                "Page 1",
                "Q/BG 通号（北京）轨道工业集团有限公司企业标准 Q/BG 4301.1—2018 "
                "生产环境通用工艺规程 2018-04-13 发布 2018-04-20 实施 集团有限公司发布",
            ),
            (
                "Page 2",
                "Q/BG 4301.1—2018 目次 前言 ...... II 1 范围 ...... 1 "
                "2 规范性引用文件 ...... 1 3 术语和定义 ...... 1",
            ),
            (
                "Page 3",
                "版本 更改内容 更改单编号 更改人 更改日期 实施日期 A 初版发行",
            ),
            (
                "Page 2",
                "...... 5 6 记录表单 ...... 6 参考文献 ...... 7",
            ),
            (
                "Page 3",
                "前言 本标准按照 GB/T 1.1 给出的规则起草。本标准主要起草人，本标准为首次发布。",
            ),
            (
                "Page 22",
                "| 附 录 A | | --- | | （规范性附录） | | 物资存贮期限及贮存包装要求 |",
            ),
        ],
    )
    def test_low_value_teaching_evidence_is_filtered(self, heading, content):
        """封面、目录、版本记录和空附录标题不应作为教学证据。"""
        assert _is_low_value_teaching_evidence({
            "heading": heading,
            "section": "",
            "content": content,
            "metadata": {},
        }) is True

    def test_substantive_appendix_is_kept(self):
        """包含实际操作要求的附录应保留。"""
        assert _is_low_value_teaching_evidence({
            "heading": "附录 A",
            "section": "",
            "content": "进入受限空间前，必须完成气体检测、通风和监护人确认。",
            "metadata": {},
        }) is False

    def test_passed_section_summary_uses_prepared_lesson_closure(self):
        """通过 Checkpoint 后应使用章节真实小结，不显示通用证据话术。"""
        section = {
            "title": "识别呆滞物料",
            "teachingScript": {
                "summary": "识别要有数据依据，发现后必须进入申报和评审流程。",
            },
        }

        content = _passed_section_summary(section, "已验证：能判断场景。")

        assert "识别要有数据依据" in content
        assert "已验证：能判断场景" in content
        assert "回顾关键知识点" not in content
        assert "证据出处" not in content

    @patch(_PATCH_EVIDENCE, return_value=[
        {"chunk_id": "c-page-1", "document_id": "doc-page-1", "heading": "Page 1", "content": "分页片段", "metadata": {}},
        {"chunk_id": "c-page-3", "document_id": "doc-page-3", "heading": "Page 3", "content": "分页片段", "metadata": {}},
    ])
    def test_plan_content_uses_saved_learning_plan_summary(self, _mock_evidence):
        """PLAN 阶段展示已生成学习计划，而不是原始 Page 召回列表。"""
        state_row = _make_state_row("INIT")
        state_row["plan_id"] = "plan-001"
        plan_row = {
            "plan_id": "plan-001",
            "status": "published",
            "documents": [
                {"documentId": "doc-a", "title": "安全操作总览", "relevance": 0.95, "abilityGroup": "基础认知", "difficulty": "basic"},
                {"documentId": "doc-b", "title": "设备维护流程", "relevance": 0.82, "abilityGroup": "作业流程", "difficulty": "normal"},
            ],
            "reading_order": ["doc-a", "doc-b"],
            "recommend_reason": "先建立安全操作全局认知，再学习设备维护流程。",
            "evidence_chunk_ids": ["chunk-a", "chunk-b"],
        }

        content, _citations = _plan_content(_PlanSession(plan_row), "kb-1", state_row)

        assert "先建立安全操作全局认知" in content
        assert "安全操作总览" in content
        assert "设备维护流程" in content
        assert "Page 1" not in content
        assert "Page 3" not in content

    @patch(_PATCH_EVIDENCE)
    def test_current_evidence_follows_learning_plan_reading_order(self, mock_evidence):
        """TEACH 阶段按学习计划 readingOrder 选择当前章节材料。"""
        mock_evidence.return_value = [
            {"chunk_id": "chunk-b", "document_id": "doc-b", "heading": "Page 3", "content": "第二章正文", "metadata": {}},
            {"chunk_id": "chunk-a", "document_id": "doc-a", "heading": "Page 1", "content": "第一章正文", "metadata": {}},
        ]
        state_row = _make_state_row("TEACH", section_index=1)
        state_row["plan_id"] = "plan-001"
        plan_row = {
            "plan_id": "plan-001",
            "status": "published",
            "documents": [
                {"documentId": "doc-a", "title": "安全操作总览", "relevance": 0.95, "abilityGroup": "基础认知", "difficulty": "basic"},
                {"documentId": "doc-b", "title": "设备维护流程", "relevance": 0.82, "abilityGroup": "作业流程", "difficulty": "normal"},
            ],
            "reading_order": ["doc-a", "doc-b"],
            "recommend_reason": "先建立安全操作全局认知，再学习设备维护流程。",
            "evidence_chunk_ids": ["chunk-a", "chunk-b"],
        }

        content, citations = _current_evidence(_PlanSession(plan_row), "app-1", "kb-1", state_row)

        assert "设备维护流程" in content
        assert "第二章正文" in content
        assert citations[0].documentId == "doc-b"

    @patch(_PATCH_EVIDENCE)
    def test_current_section_aggregates_multiple_useful_evidence(self, mock_evidence):
        """当前小节应过滤低价值片段，并聚合多份正文证据。"""
        mock_evidence.return_value = [
            {"chunk_id": "cover", "document_id": "doc-a", "heading": "封面", "section": "", "content": "企业标准发布页", "metadata": {}},
            {"chunk_id": "chunk-a", "document_id": "doc-a", "heading": "作业前确认", "section": "操作要求", "content": "启动设备前必须确认防护罩闭合。", "metadata": {}},
            {"chunk_id": "chunk-b", "document_id": "doc-b", "heading": "异常处置", "section": "风险控制", "content": "发现异常振动时应立即停机并上报。", "metadata": {}},
        ]
        state_row = _make_state_row("TEACH", metadata={
            "inputs": {
                "jobTitle": "设备操作员",
                "courseSnapshot": {
                    "sections": [{
                        "sectionId": "section-1",
                        "title": "设备启动与异常处置",
                        "learningObjective": "能够安全启动设备并识别异常。",
                        "checkpointCriteria": ["说明启动前确认项", "说明异常处置动作"],
                        "sourceDocumentIds": ["doc-a", "doc-b"],
                        "evidenceChunkIds": ["chunk-a", "chunk-b"],
                    }]
                },
            }
        })

        content, citations = _current_evidence(MagicMock(), "app-1", "kb-1", state_row)

        assert "能够安全启动设备并识别异常" in content
        assert "核心解释" in content
        assert "适用条件" in content
        assert "风险点" in content
        assert "具体作业案例" in content
        assert "启动设备前必须确认防护罩闭合" in content
        assert "发现异常振动时应立即停机并上报" in content
        assert "企业标准发布页" not in content
        assert {citation.documentId for citation in citations} == {"doc-a", "doc-b"}
        assert {citation.chunkId for citation in citations} == {"chunk-a", "chunk-b"}
        assert mock_evidence.call_args_list[0].kwargs["chunk_ids"] == ["chunk-a", "chunk-b"]

    @patch(_PATCH_EVIDENCE)
    def test_current_section_uses_prepared_teaching_script_without_chunk_text(self, mock_evidence):
        """已生成章节讲稿时，课堂只展示教学内容，Chunk 仅保留为 Citation。"""
        mock_evidence.return_value = [
            {
                "chunk_id": "chunk-a",
                "document_id": "doc-a",
                "heading": "判定条件",
                "section": "第三章",
                "content": "存储时间超过1年且期间无任何出入库动态。",
                "metadata": {},
            },
        ]
        state_row = _make_state_row("TEACH", metadata={
            "inputs": {
                "courseSnapshot": {
                    "sections": [{
                        "sectionId": "section-1",
                        "title": "识别呆滞物料",
                        "learningObjective": "能够根据库存状态判断是否进入评审。",
                        "sourceDocumentIds": ["doc-a"],
                        "evidenceChunkIds": ["chunk-a"],
                        "teachingScript": {
                            "opening": "一批物料一年没有出入库，你会怎么处理？",
                            "explanation": "先根据库存动态识别，再提交主管复核和跨部门评审，不能直接报废。",
                            "scenario": "库管工核对台账后填写报表，由仓库主管复核判断依据。",
                            "interactionQuestions": ["质量合格的物料是否也可能呆滞？"],
                            "summary": "识别要有依据，处置要经过评审。",
                        },
                    }]
                }
            }
        })

        content, citations = _current_evidence(MagicMock(), "app-1", "kb-1", state_row)

        assert "情境导入" in content
        assert "教师讲解" in content
        assert "工作案例" in content
        assert "想一想" in content
        assert "本节小结" in content
        assert "参考证据" not in content
        assert "存储时间超过1年且期间无任何出入库动态" not in content
        assert citations[0].chunkId == "chunk-a"

    @patch(_PATCH_EVIDENCE)
    def test_current_section_rejects_all_low_value_evidence(self, mock_evidence):
        """全部证据均为低价值时应提示复核，不把封面重新展示为讲解正文。"""
        mock_evidence.return_value = [
            {"chunk_id": "cover", "document_id": "doc-a", "heading": "封面", "section": "", "content": "企业标准发布页", "metadata": {}},
        ]
        state_row = _make_state_row("TEACH", metadata={
            "inputs": {
                "courseSnapshot": {
                    "sections": [{
                        "sectionId": "section-1",
                        "title": "安全要求",
                        "sourceDocumentIds": ["doc-a"],
                    }]
                }
            }
        })

        content, citations = _current_evidence(MagicMock(), "app-1", "kb-1", state_row)

        assert "仅召回低教学价值片段" in content
        assert "企业标准发布页" not in content
        assert citations == []

    @patch(_PATCH_EVIDENCE)
    def test_switching_section_changes_content_and_citations(self, mock_evidence):
        """切换当前小节后，教学材料和 Citation 应随小节证据变化。"""
        def evidence_for_section(_session, _kb_id, _query, **kwargs):
            document_id = kwargs["document_ids"][0]
            return [{
                "chunk_id": f"chunk-{document_id}",
                "document_id": document_id,
                "heading": "正文",
                "section": "",
                "content": f"{document_id} 的教学正文",
                "metadata": {},
            }]

        mock_evidence.side_effect = evidence_for_section
        snapshot = {
            "sections": [
                {"sectionId": "section-a", "title": "启动前检查", "sourceDocumentIds": ["doc-a"]},
                {"sectionId": "section-b", "title": "异常停机", "sourceDocumentIds": ["doc-b"]},
            ]
        }
        first_state = _make_state_row("TEACH", section_index=0, metadata={"inputs": {"courseSnapshot": snapshot}})
        second_state = _make_state_row("TEACH", section_index=1, metadata={"inputs": {"courseSnapshot": snapshot}})

        first_content, first_citations = _current_evidence(MagicMock(), "app-1", "kb-1", first_state)
        second_content, second_citations = _current_evidence(MagicMock(), "app-1", "kb-1", second_state)

        assert first_content != second_content
        assert first_citations[0].documentId == "doc-a"
        assert second_citations[0].documentId == "doc-b"
