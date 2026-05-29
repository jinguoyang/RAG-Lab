"""培训报表与薄弱点统计 DTO。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class WeaknessItemDTO(BaseModel):
    """薄弱点条目。"""

    questionId: str
    content: str
    failCount: int
    failRate: float


class TrainingReportDTO(BaseModel):
    """培训报表汇总。"""

    appId: str
    completionRate: float
    averageScore: float
    passedCount: int
    totalCount: int
    failedQuestionCount: int
    weaknesses: list[WeaknessItemDTO] = Field(default_factory=list)
