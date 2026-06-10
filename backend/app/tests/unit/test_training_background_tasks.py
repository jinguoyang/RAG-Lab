"""员工培训后台任务执行器回归测试。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.routes import tasks, training_plans, training_questions
from app.schemas.training_plan import PlanDraftRequest
from app.schemas.training_question import QuestionDraftRequest
from app.services.task_manager import TaskStatus, TaskType, task_manager


class _FakeSession:
    """记录后台任务是否正确释放独立数据库会话。"""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_completed_plan_task_list_keeps_result_for_page_recovery():
    """学习计划页重新加载任务列表时，应能恢复已完成草稿的结果。"""
    task = task_manager.create_task(TaskType.PLAN_GENERATION, "生成学习计划: 财务")
    task_manager.complete_task(task.id, result={"planId": "plan-001", "jobTitle": "财务"})

    try:
        response = tasks.list_tasks()
        summary = next(item for item in response.tasks if item.id == task.id)

        assert summary.result == {"planId": "plan-001", "jobTitle": "财务"}
    finally:
        task_manager._tasks.pop(task.id, None)


@pytest.mark.parametrize(
    ("runner", "payload", "service_name", "result"),
    [
        (
            training_plans._run_plan_draft_task,
            PlanDraftRequest(jobTitle="财务", jobDescription="测试岗位"),
            "create_plan_draft",
            SimpleNamespace(model_dump=lambda: {"planId": "plan-001"}),
        ),
        (
            training_questions._run_question_draft_task,
            QuestionDraftRequest(planId="plan-001", jobTitle="财务"),
            "create_question_drafts",
            [SimpleNamespace(model_dump=lambda: {"questionId": "question-001"})],
        ),
    ],
)
def test_training_background_task_uses_project_session_factory(
    monkeypatch,
    runner,
    payload,
    service_name,
    result,
):
    """后台执行器应使用项目会话工厂，并将任务推进到完成状态。"""
    route_module = training_plans if runner is training_plans._run_plan_draft_task else training_questions
    session = _FakeSession()
    task = task_manager.create_task(TaskType.OTHER, "后台任务回归测试")

    monkeypatch.setattr("app.core.database.get_session_factory", lambda: lambda: session)
    monkeypatch.setattr(route_module, service_name, lambda *_args, **_kwargs: result)

    try:
        runner(task.id, "test-credential", payload)

        assert task.status == TaskStatus.COMPLETED
        assert session.closed is True
    finally:
        task_manager._tasks.pop(task.id, None)


@pytest.mark.parametrize(
    ("runner", "payload"),
    [
        (
            training_plans._run_plan_draft_task,
            PlanDraftRequest(jobTitle="财务", jobDescription="测试岗位"),
        ),
        (
            training_questions._run_question_draft_task,
            QuestionDraftRequest(planId="plan-001", jobTitle="财务"),
        ),
    ],
)
def test_training_background_task_reports_session_initialization_failure(
    monkeypatch,
    runner,
    payload,
):
    """数据库会话初始化失败时，任务应进入失败终态而不是永久 pending。"""
    task = task_manager.create_task(TaskType.OTHER, "后台任务初始化失败测试")

    def raise_session_error():
        raise RuntimeError("session initialization failed")

    monkeypatch.setattr("app.core.database.get_session_factory", raise_session_error)

    try:
        runner(task.id, "test-credential", payload)

        assert task.status == TaskStatus.FAILED
        assert task.started_at is not None
        assert task.error == "session initialization failed"
    finally:
        task_manager._tasks.pop(task.id, None)
