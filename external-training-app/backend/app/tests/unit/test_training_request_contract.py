"""外部培训应用请求契约测试。"""

import pytest
from pydantic import ValidationError

from app.schemas.training_classroom import ClassroomSessionCreateRequest
from app.schemas.training_plan import TrainingPlanDraftRequest
from app.schemas.training_question import TrainingQuestionDraftRequest


@pytest.mark.parametrize(
    ("schema_cls", "payload"),
    [
        (TrainingPlanDraftRequest, {"appId": "app-001", "jobTitle": "安全员"}),
        (TrainingQuestionDraftRequest, {"appId": "app-001", "planId": "plan-001"}),
        (ClassroomSessionCreateRequest, {"appId": "app-001", "endUserId": "user-001"}),
    ],
)
def test_external_training_requests_reject_app_id(schema_cls, payload):
    """外部应用请求体也不接受 appId，避免形成双重 App 来源。"""
    with pytest.raises(ValidationError):
        schema_cls(**payload)
