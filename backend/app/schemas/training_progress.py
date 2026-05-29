"""员工学习进度与答题记录 DTO。"""
from __future__ import annotations

from pydantic import BaseModel


class ProgressDTO(BaseModel):
    """学习进度。"""

    sessionId: str
    appId: str
    endUserId: str
    currentSectionIndex: int
    completedSections: int
    totalSections: int
    lastScore: int | None = None
    status: str
    updatedAt: str


class AnswerRecordDTO(BaseModel):
    """答题记录。"""

    answerId: str
    sessionId: str
    questionId: str
    questionType: str
    answer: str
    score: int | None = None
    isCorrect: bool | None = None
    explanation: str | None = None
    createdAt: str
