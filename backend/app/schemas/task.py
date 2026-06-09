"""后台任务相关 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LogEntryDTO(BaseModel):
    timestamp: datetime
    level: str = Field(description="info, warning, error, token")
    message: str
    data: dict[str, Any] | None = None


class TaskSummaryDTO(BaseModel):
    id: str
    type: str
    title: str
    status: str
    createdAt: datetime
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    error: str | None = None


class TaskDetailDTO(BaseModel):
    id: str
    type: str
    title: str
    status: str
    createdAt: datetime
    startedAt: datetime | None = None
    completedAt: datetime | None = None
    logs: list[LogEntryDTO] = Field(default_factory=list)
    result: Any = None
    error: str | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskSummaryDTO]
