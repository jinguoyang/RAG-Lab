"""员工培训 Agent 端到端集成验收测试。"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas.training_classroom import (
    ClassroomEventSubmitRequest,
    ClassroomSessionCreateRequest,
)
from app.schemas.training_plan import PlanDraftRequest
from app.schemas.training_question import QuestionDraftRequest
from app.tables import (
    training_answer_records,
    training_classroom_sessions,
    training_plans,
    training_progress_records,
    training_questions,
    training_skill_calls,
)
from app.tests.integration.test_employee_training_agent_runtime import _insert_training_app


def _insert_published_question(db, app_id, question_type="single_choice"):
    """直接插入已发布题目，避免依赖 LLM 和草稿流程。"""
    now = datetime.now(UTC)
    question_id = uuid4()
    if question_type == "single_choice":
        content = "现场安全员进入作业区域前应首先做什么？"
        options = [
            {"label": "A", "text": "佩戴个人防护装备并检查入场证件"},
            {"label": "B", "text": "直接进入开始作业"},
        ]
        correct_answer = "A"
        explanation = "进入作业区域前必须佩戴防护装备并验证入场资格。"
    else:
        content = "设备点检发现异常时应立即停机并记录。"
        options = [{"label": "true", "text": "正确"}, {"label": "false", "text": "错误"}]
        correct_answer = "true"
        explanation = "设备异常必须停机记录，不能继续使用。"

    db.execute(
        training_questions.insert().values(
            question_id=question_id,
            plan_id=uuid4(),
            app_id=app_id,
            question_type=question_type,
            category="practice",
            content=content,
            options=options,
            correct_answer=correct_answer,
            explanation=explanation,
            rubric=None,
            evidence_chunk_ids=[],
            status="published",
            metadata={},
            created_at=now,
            created_by=None,
            updated_at=now,
            updated_by=None,
        )
    )
    return str(question_id)


@pytest.fixture()
def app_with_questions(db):
    """创建包含已发布题目的培训 App。"""
    credential, app_id = _insert_training_app(db)
    q1_id = _insert_published_question(db, app_id, "single_choice")
    q2_id = _insert_published_question(db, app_id, "true_false")
    return credential, app_id, q1_id, q2_id


# ---------------------------------------------------------------------------
# 测试用例 1: 完整学习流程
# ---------------------------------------------------------------------------


def test_e2e_complete_learning_flow(db, app_with_questions):
    """从创建会话到完成课程的完整链路。"""
    credential, app_id, q1_id, q2_id = app_with_questions

    from app.services.training_classroom_service import (
        create_classroom_session,
        submit_classroom_event,
    )

    # 1. 创建课堂会话
    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(
            appId=app_id, endUserId="e2e-employee-001", inputs={"jobTitle": "现场安全员"}
        ),
    )
    assert created.currentState == "INIT"

    # 2. start -> PLAN
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(eventType="start", payload={}),
    )
    assert r.classroomState == "PLAN"
    assert "本课程将按以下材料展开" in r.visibleContent

    # 3. continue -> TEACH
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(eventType="continue", payload={}),
    )
    assert r.classroomState == "TEACH"
    assert r.uiActions[0].actionType == "button_group"

    # 4. continue -> CHECK_UNDERSTAND
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(eventType="continue", payload={}),
    )
    assert r.classroomState == "CHECK_UNDERSTAND"
    assert r.control.requiresInput is True

    # 5. continue -> QUIZ
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(eventType="continue", payload={}),
    )
    assert r.classroomState == "QUIZ"
    assert any(a.actionType in ("single_choice", "true_false") for a in r.uiActions)

    # 6. submit_answer -> GRADE (正确答案)
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(
            eventType="submit_answer",
            payload={"questionId": q1_id, "answer": "A"},
        ),
    )
    assert r.classroomState == "GRADE"
    assert "得分：100" in r.visibleContent

    # 7. continue -> REVIEW
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(eventType="continue", payload={}),
    )
    assert r.classroomState == "REVIEW"

    # 8. continue -> SUMMARY
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(eventType="continue", payload={}),
    )
    assert r.classroomState == "SUMMARY"

    # 9. complete -> COMPLETED (单节课程直接完成)
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(eventType="complete", payload={}),
    )
    assert r.classroomState == "COMPLETED"
    assert "课程已完成" in r.visibleContent

    # 验证数据库会话状态
    session_row = (
        db.execute(
            training_classroom_sessions.select().where(
                training_classroom_sessions.c.session_id == created.sessionId
            )
        )
        .mappings()
        .one()
    )
    assert session_row["current_state"] == "COMPLETED"


# ---------------------------------------------------------------------------
# 测试用例 2: 未通过测验重试流程
# ---------------------------------------------------------------------------


def test_e2e_quiz_retry_after_failure(db, app_with_questions):
    """未通过测验后重试并最终通过。"""
    credential, app_id, q1_id, q2_id = app_with_questions

    from app.services.training_classroom_service import (
        create_classroom_session,
        submit_classroom_event,
    )

    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(
            appId=app_id, endUserId="e2e-employee-002", inputs={"jobTitle": "现场安全员"}
        ),
    )
    # 推进到 QUIZ
    submit_classroom_event(db, credential, created.sessionId, ClassroomEventSubmitRequest(eventType="start", payload={}))
    submit_classroom_event(db, credential, created.sessionId, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(db, credential, created.sessionId, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    r = submit_classroom_event(db, credential, created.sessionId, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    assert r.classroomState == "QUIZ"

    # 提交错误答案 -> GRADE (未通过)
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(
            eventType="submit_answer",
            payload={"questionId": q1_id, "answer": "B"},
        ),
    )
    assert r.classroomState == "GRADE"
    assert "得分：0" in r.visibleContent
    assert "未达到通过线" in r.visibleContent

    # continue -> REVIEW (显示错题和重试选项)
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(eventType="continue", payload={}),
    )
    assert r.classroomState == "REVIEW"
    assert "测验未通过" in r.visibleContent
    event_types = {btn["eventType"] for btn in r.uiActions[0].data["buttons"]}
    assert "retry_quiz" in event_types

    # retry_quiz -> QUIZ
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(eventType="retry_quiz", payload={}),
    )
    assert r.classroomState == "QUIZ"

    # 提交正确答案 -> GRADE (通过)
    r = submit_classroom_event(
        db, credential, created.sessionId,
        ClassroomEventSubmitRequest(
            eventType="submit_answer",
            payload={"questionId": q1_id, "answer": "A"},
        ),
    )
    assert r.classroomState == "GRADE"
    assert "得分：100" in r.visibleContent
    assert "达到通过线" in r.visibleContent


# ---------------------------------------------------------------------------
# 测试用例 3: 进度和答题记录
# ---------------------------------------------------------------------------


def test_e2e_progress_and_answer_records(db, app_with_questions):
    """完成学习流程后应有进度记录和答题记录。"""
    credential, app_id, q1_id, q2_id = app_with_questions

    from app.services.training_classroom_service import (
        create_classroom_session,
        submit_classroom_event,
    )

    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(
            appId=app_id, endUserId="e2e-employee-003", inputs={"jobTitle": "现场安全员"}
        ),
    )
    sid = created.sessionId

    # 推进到 QUIZ 并提交答案
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="start", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(
        db, credential, sid,
        ClassroomEventSubmitRequest(
            eventType="submit_answer",
            payload={"questionId": q1_id, "answer": "A"},
        ),
    )

    # 验证答题记录
    answer_rows = (
        db.execute(
            training_answer_records.select().where(
                training_answer_records.c.session_id == sid
            )
        )
        .mappings()
        .all()
    )
    assert len(answer_rows) == 1
    assert answer_rows[0]["score"] == 100
    assert answer_rows[0]["is_correct"] is True
    assert answer_rows[0]["app_id"] == app_id
    assert answer_rows[0]["end_user_id"] == "e2e-employee-003"

    # 完成课程以触发进度更新
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="complete", payload={}))

    # 验证进度记录
    progress_rows = (
        db.execute(
            training_progress_records.select().where(
                training_progress_records.c.session_id == sid
            )
        )
        .mappings()
        .all()
    )
    assert len(progress_rows) >= 1
    progress = progress_rows[0]
    assert progress["app_id"] == app_id
    assert progress["end_user_id"] == "e2e-employee-003"
    assert progress["status"] == "completed"

    # 验证进度按 appId+sessionId+endUserId 隔离
    other_progress = (
        db.execute(
            training_progress_records.select().where(
                training_progress_records.c.session_id == "non-existent-session"
            )
        )
        .mappings()
        .all()
    )
    assert len(other_progress) == 0


# ---------------------------------------------------------------------------
# 测试用例 4: 报表统计
# ---------------------------------------------------------------------------


def test_e2e_training_report(db, app_with_questions):
    """完成学习流程后报表应包含正确的统计数据。"""
    credential, app_id, q1_id, q2_id = app_with_questions

    from app.services.training_classroom_service import (
        create_classroom_session,
        submit_classroom_event,
    )
    from app.services.training_report_service import get_training_report

    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(
            appId=app_id, endUserId="e2e-employee-004", inputs={"jobTitle": "现场安全员"}
        ),
    )
    sid = created.sessionId

    # 完成完整流程
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="start", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(
        db, credential, sid,
        ClassroomEventSubmitRequest(
            eventType="submit_answer",
            payload={"questionId": q1_id, "answer": "A"},
        ),
    )
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="complete", payload={}))

    # 获取报表
    report = get_training_report(db, app_id)

    assert report.appId == app_id
    assert report.totalCount >= 1
    assert report.passedCount >= 1
    assert report.completionRate > 0
    assert report.averageScore > 0


# ---------------------------------------------------------------------------
# 测试用例 5: 断线续接
# ---------------------------------------------------------------------------


def test_e2e_session_resume_metadata(db, app_with_questions):
    """TEACH 状态下的会话应返回 pendingActions 和 contextSummary。"""
    credential, app_id, q1_id, q2_id = app_with_questions

    from app.services.training_classroom_service import (
        create_classroom_session,
        get_classroom_session,
        submit_classroom_event,
    )

    created = create_classroom_session(
        db,
        credential,
        ClassroomSessionCreateRequest(
            appId=app_id, endUserId="e2e-employee-005", inputs={"jobTitle": "现场安全员"}
        ),
    )
    sid = created.sessionId

    # 推进到 TEACH
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="start", payload={}))
    submit_classroom_event(db, credential, sid, ClassroomEventSubmitRequest(eventType="continue", payload={}))

    # 获取会话详情（模拟断线续接）
    detail = get_classroom_session(db, sid, credential=credential)

    assert detail.currentState == "TEACH"
    assert detail.metadata is not None

    # 验证 pendingActions
    pending = detail.metadata.get("pendingActions", [])
    assert len(pending) > 0
    event_types = {a["eventType"] for a in pending}
    assert "continue" in event_types

    # 验证 contextSummary 非空（有 assistant 消息）
    assert detail.metadata.get("contextSummary") is not None
    assert len(detail.metadata["contextSummary"]) > 0


# ---------------------------------------------------------------------------
# 测试用例 6: 跨 App 权限隔离
# ---------------------------------------------------------------------------


def test_e2e_cross_app_session_isolation(db, app_with_questions):
    """用 App B 的 credential 访问 App A 的课堂应被拒绝。"""
    credential_a, app_id_a, _, _ = app_with_questions

    from app.services.app_runtime_service import _hash_api_key
    from app.services.training_classroom_service import (
        create_classroom_session,
        submit_classroom_event,
    )
    from app.services.training_agent_service import TrainingAgentConflictError
    from app.tables import rag_app_api_keys

    # 创建第二个 App（使用不同的 API Key）
    credential_b, app_id_b = _insert_training_app(db)
    # _insert_training_app 使用相同的 key，需要替换 App B 的 key 为不同的值
    plain_key_b = "rlak_training_agent_platform_b"
    db.execute(
        rag_app_api_keys.update()
        .where(rag_app_api_keys.c.app_id == app_id_b)
        .values(key_hash=_hash_api_key(plain_key_b), key_prefix=plain_key_b[:16])
    )
    db.commit()

    # 用 App A 的 credential 创建会话
    created = create_classroom_session(
        db,
        credential_a,
        ClassroomSessionCreateRequest(
            appId=app_id_a, endUserId="e2e-employee-006", inputs={"jobTitle": "现场安全员"}
        ),
    )

    # 用 App B 的 credential 尝试操作 App A 的会话
    with pytest.raises(TrainingAgentConflictError):
        submit_classroom_event(
            db,
            plain_key_b,
            created.sessionId,
            ClassroomEventSubmitRequest(eventType="start", payload={}),
        )
