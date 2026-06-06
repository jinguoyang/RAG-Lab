"""课前数据链路平台侧接口服务测试。"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4
from unittest.mock import patch

import pytest

from app.schemas.training_post_quiz import PostQuizAnswerDTO, PostQuizStartRequest, PostQuizSubmitRequest
from app.schemas.training_question import (
    QuestionAppealRequest,
    QuestionAppealResolveRequest,
    QuestionOptionDTO,
    QuestionReviewRequest,
    QuestionUpdateRequest,
)
from app.services.training_agent_service import TrainingAgentConflictError
from app.tables import (
    training_post_quizzes,
    training_progress_records,
    training_question_appeals,
    training_questions,
)
from app.tests.integration.test_employee_training_agent_runtime import _insert_training_app


def _insert_question(db, app_id: str, document_id: str, question_type: str, answer: str = "A") -> str:
    """插入指定文档的已发布题目。"""
    now = datetime.now(UTC)
    question_id = str(uuid4())
    if question_type == "single_choice":
        options = [
            {"label": "A", "text": "正确做法"},
            {"label": "B", "text": "错误做法"},
            {"label": "C", "text": "无关选项"},
            {"label": "D", "text": "风险选项"},
        ]
        correct_answer = answer
        rubric = None
    elif question_type == "true_false":
        options = [{"label": "true", "text": "正确"}, {"label": "false", "text": "错误"}]
        correct_answer = answer
        rubric = None
    else:
        options = []
        correct_answer = None
        rubric = {
            "totalScore": 5,
            "criteria": [
                {"name": "依据准确", "score": 2, "description": "依据材料回答。"},
                {"name": "流程完整", "score": 2, "description": "覆盖主要流程。"},
                {"name": "表达清晰", "score": 1, "description": "表达清楚。"},
            ],
        }
    db.execute(
        training_questions.insert().values(
            question_id=question_id,
            plan_id="external-plan-001",
            app_id=app_id,
            question_type=question_type,
            category="practice",
            content=f"{question_type} 题目",
            options=options,
            correct_answer=correct_answer,
            explanation="题目解析",
            rubric=rubric,
            evidence_chunk_ids=[],
            status="published",
            metadata={"documentId": document_id},
            created_at=now,
            created_by=None,
            updated_at=now,
            updated_by=None,
        )
    )
    return question_id


def _insert_completed_progress(db, app_id: str, session_id: str, end_user_id: str) -> None:
    """插入已完成学习进度，用于课后测验门禁。"""
    now = datetime.now(UTC)
    db.execute(
        training_progress_records.insert().values(
            progress_id=str(uuid4()),
            session_id=session_id,
            app_id=app_id,
            end_user_id=end_user_id,
            plan_id="external-plan-001",
            current_section_index=1,
            completed_sections=1,
            total_sections=1,
            last_score=100,
            status="completed",
            metadata={},
            created_at=now,
            updated_at=now,
        )
    )


def _seed_question_pool(db, app_id: str, document_id: str) -> dict[str, list[str]]:
    """按 5 题课后测验需要插入 2/2/1 题池。"""
    return {
        "single_choice": [
            _insert_question(db, app_id, document_id, "single_choice", "A"),
            _insert_question(db, app_id, document_id, "single_choice", "A"),
        ],
        "true_false": [
            _insert_question(db, app_id, document_id, "true_false", "true"),
            _insert_question(db, app_id, document_id, "true_false", "true"),
        ],
        "subjective": [
            _insert_question(db, app_id, document_id, "subjective"),
        ],
    }


def test_training_document_query_lists_current_app_documents(db):
    """文档查询应从当前 App 知识库返回可选文档。"""
    credential, _app_id = _insert_training_app(db)
    from app.services.training_document_service import list_training_documents

    docs = list_training_documents(db, credential, query="安全")

    assert len(docs) == 1
    assert docs[0].title == "现场安全制度"
    assert docs[0].summary


def test_question_update_and_appeal(db):
    """管理员可修改题目，学员可上报题目异议。"""
    credential, app_id = _insert_training_app(db)
    document_id = str(uuid4())
    question_id = _insert_question(db, app_id, document_id, "subjective")

    from app.services.training_question_service import create_question_appeal, resolve_question_appeal, update_question

    updated = update_question(
        db,
        question_id,
        QuestionUpdateRequest(
            content="修改后的主观题",
            rubric={"totalScore": 100, "criteria": [{"name": "流程说明特别长", "score": 100}]},
            evidenceChunkIds=["chunk-001"],
        ),
        "admin-001",
    )
    assert updated.content == "修改后的主观题"
    assert updated.rubric["totalScore"] == 5
    assert updated.rubric["criteria"][0]["name"] == "流程说明特别长"[:10]

    appeal = create_question_appeal(
        db,
        credential,
        question_id,
        QuestionAppealRequest(endUserId="employee-001", reason="题目答案和教材表述不一致。"),
    )
    assert appeal.status == "open"
    row = db.execute(training_question_appeals.select()).mappings().one()
    assert row["question_id"] == question_id
    assert row["end_user_id"] == "employee-001"

    resolved = resolve_question_appeal(
        db,
        appeal.appealId,
        QuestionAppealResolveRequest(status="resolved", notes="已调整解析。"),
        "admin-001",
    )
    assert resolved.status == "resolved"


def test_question_review_with_app_key_publishes_question(db):
    """ex-app 通过 App API Key 审核题目后，平台题库状态应变为 published。"""
    credential, app_id = _insert_training_app(db)
    question_id = _insert_question(db, app_id, str(uuid4()), "single_choice")
    db.execute(
        training_questions.update()
        .where(training_questions.c.question_id == question_id)
        .values(status="draft")
    )
    from app.services.training_question_service import review_question_with_credential

    reviewed = review_question_with_credential(
        db,
        credential,
        question_id,
        QuestionReviewRequest(decision="approved", notes="ok"),
    )

    assert reviewed.status == "published"


def test_post_quiz_requires_completed_progress(db):
    """未学完文档前不得开始课后测验。"""
    credential, app_id = _insert_training_app(db)
    document_id = str(uuid4())
    _seed_question_pool(db, app_id, document_id)
    from app.services.training_post_quiz_service import start_post_quiz

    with pytest.raises(TrainingAgentConflictError, match="DOCUMENT_LEARNING_NOT_COMPLETED"):
        start_post_quiz(
            db,
            credential,
            PostQuizStartRequest(
                sessionId="session-001",
                endUserId="employee-001",
                documentId=document_id,
                count=5,
            ),
        )


def test_post_quiz_selects_ratio_and_scores_submission(db):
    """课后测验应按 2/2/1 抽题并按 5 分制返回结果。"""
    credential, app_id = _insert_training_app(db)
    document_id = str(uuid4())
    session_id = str(uuid4())
    _insert_completed_progress(db, app_id, session_id, "employee-001")
    _seed_question_pool(db, app_id, document_id)
    from app.services.training_post_quiz_service import start_post_quiz, submit_post_quiz
    from app.services.training_grading_service import SubjectiveGradeResult

    quiz = start_post_quiz(
        db,
        credential,
        PostQuizStartRequest(
            sessionId=session_id,
            endUserId="employee-001",
            documentId=document_id,
            count=5,
        ),
    )
    assert [item.questionType for item in quiz.questions].count("single_choice") == 2
    assert [item.questionType for item in quiz.questions].count("true_false") == 2
    assert [item.questionType for item in quiz.questions].count("subjective") == 1

    answers: list[PostQuizAnswerDTO] = []
    for question in quiz.questions:
        if question.questionType == "single_choice":
            answers.append(PostQuizAnswerDTO(questionId=question.questionId, answer="A"))
        elif question.questionType == "true_false":
            answers.append(PostQuizAnswerDTO(questionId=question.questionId, answer="true"))
        else:
            answers.append(PostQuizAnswerDTO(questionId=question.questionId, answer="按流程处理并记录。"))

    with patch("app.services.training_post_quiz_service.grade_subjective_answer") as mock_grade:
        mock_grade.return_value = SubjectiveGradeResult(score=90, reason="覆盖考点。")
        result = submit_post_quiz(
            db,
            credential,
            quiz.quizId,
            PostQuizSubmitRequest(endUserId="employee-001", answers=answers),
    )

    assert result.passed is True
    assert result.score == 4.9
    stored_quiz = db.execute(training_post_quizzes.select()).mappings().one()
    assert stored_quiz["status"] == "submitted"
    assert stored_quiz["passed"] is True
    progress = db.execute(training_progress_records.select()).mappings().one()
    assert document_id in progress["metadata"]["completedDocumentIds"]
