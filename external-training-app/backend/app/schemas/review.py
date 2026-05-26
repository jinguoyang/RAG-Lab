"""审核 schemas。"""
from typing import Any
from pydantic import BaseModel, Field

class ReviewTaskResponse(BaseModel):
    id: str
    platformDraftId: str | None = None
    platformPlanId: str | None = None
    reviewType: str
    status: str
    submittedPayload: dict[str, Any] = Field(default_factory=dict)
    createdAt: str

class ReviewSubmitRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    notes: str = ""
    adjustments: dict[str, Any] | None = None
