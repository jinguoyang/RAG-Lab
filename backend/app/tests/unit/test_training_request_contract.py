"""员工培训三方请求契约测试。"""

import pytest
from pydantic import ValidationError

from app.schemas.training_classroom import ClassroomSessionCreateRequest
from app.schemas.training_plan import PlanDraftRequest
from app.schemas.training_question import QuestionDraftRequest


@pytest.mark.parametrize(
    ("schema_cls", "payload"),
    [
        (PlanDraftRequest, {"appId": "app-001", "jobTitle": "安全员"}),
        (QuestionDraftRequest, {"appId": "app-001", "planId": "plan-001"}),
        (ClassroomSessionCreateRequest, {"appId": "app-001", "endUserId": "user-001"}),
    ],
)
def test_training_requests_reject_app_id(schema_cls, payload):
    """三方请求不得携带 appId，平台只从 App API Key 解析 App。"""
    with pytest.raises(ValidationError):
        schema_cls(**payload)
