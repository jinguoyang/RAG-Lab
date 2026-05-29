"""培训管理端点权限边界测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.training_plans import publish_training_plan
from app.api.routes.training_questions import publish_training_question
from app.api.routes.training_reports import get_training_report_summary
from app.schemas.auth import CurrentUserResponse, UserDTO


def _current_user(platform_role: str = "platform_user") -> CurrentUserResponse:
    """构建最小当前用户对象，用于直接调用路由函数。"""
    return CurrentUserResponse(
        user=UserDTO(
            userId="user-001",
            username="user",
            displayName="普通用户",
            email="user@example.com",
            platformRole=platform_role,
            securityLevel="internal",
            status="active",
        ),
        platformPermissions=[],
        visibleKbCount=0,
    )


def test_non_admin_cannot_publish_training_plan():
    """普通用户不能发布学习计划。"""
    with pytest.raises(HTTPException) as exc_info:
        publish_training_plan("plan-001", _current_user(), MagicMock())

    assert exc_info.value.status_code == 403


def test_non_admin_cannot_publish_training_question():
    """普通用户不能发布题目。"""
    with pytest.raises(HTTPException) as exc_info:
        publish_training_question("question-001", _current_user(), MagicMock())

    assert exc_info.value.status_code == 403


def test_non_admin_cannot_read_training_report():
    """普通用户不能读取全局培训报表。"""
    with pytest.raises(HTTPException) as exc_info:
        get_training_report_summary("app-001", _current_user(), MagicMock())

    assert exc_info.value.status_code == 403


def test_admin_can_read_training_report():
    """平台管理员可以读取培训报表。"""
    with patch("app.api.routes.training_reports.get_training_report") as mock_report:
        mock_report.return_value = MagicMock()

        result = get_training_report_summary("app-001", _current_user("platform_admin"), MagicMock())

    assert result is mock_report.return_value
    mock_report.assert_called_once()
