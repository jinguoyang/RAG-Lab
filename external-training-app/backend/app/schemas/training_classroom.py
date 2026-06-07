"""课堂相关 Pydantic schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── 请求 ──────────────────────────────────────────────────────────────

class ClassroomSessionCreateRequest(BaseModel):
    """创建课堂会话请求。"""
    model_config = ConfigDict(extra="forbid")

    planId: str | None = Field(default=None, max_length=36)
    documentId: str | None = Field(default=None, max_length=128)
    endUserId: str = Field(min_length=1, max_length=128)
    inputs: dict[str, Any] | None = None


class ClassroomEventSubmitRequest(BaseModel):
    """提交课堂事件请求。"""
    eventType: str = Field(min_length=1, max_length=32)
    payload: dict[str, Any] = Field(default_factory=dict)
    query: str | None = Field(default=None, max_length=4000)


# ── DTO ───────────────────────────────────────────────────────────────

class ClassroomMessageDTO(BaseModel):
    """课堂消息。"""
    messageId: str
    role: str
    content: str
    stateAtTime: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str


class ClassroomUiActionDTO(BaseModel):
    """课堂 UI 动作。"""
    actionType: str
    data: dict[str, Any] = Field(default_factory=dict)


class ClassroomCitationDTO(BaseModel):
    """课堂引用。"""
    documentId: str | None = None
    chunkId: str | None = None
    content: str | None = None
    score: float | None = None


class ClassroomControlDTO(BaseModel):
    """课堂控制信号。"""
    canProceed: bool = True
    requiresInput: bool = False
    inputType: str | None = None


class ClassroomProgressUpdateDTO(BaseModel):
    """课堂进度更新。"""
    sectionIndex: int | None = None
    sectionTotal: int | None = None
    completedSections: int | None = None


# ── 响应 ──────────────────────────────────────────────────────────────

class ClassroomSessionResponse(BaseModel):
    """课堂会话响应。"""
    sessionId: str
    appId: str
    planId: str | None = None
    endUserId: str
    currentState: str
    currentSectionIndex: int
    createdAt: str


class ClassroomEventResponse(BaseModel):
    """课堂事件响应。"""
    eventId: str
    sessionId: str
    eventType: str
    resultState: str | None = None
    visibleContent: str
    classroomState: str
    uiActions: list[ClassroomUiActionDTO] = Field(default_factory=list)
    citations: list[ClassroomCitationDTO] = Field(default_factory=list)
    control: ClassroomControlDTO = Field(default_factory=ClassroomControlDTO)
    progressUpdate: ClassroomProgressUpdateDTO | None = None
    messages: list[ClassroomMessageDTO] = Field(default_factory=list)
    createdAt: str


class ClassroomSessionDetailResponse(BaseModel):
    """课堂会话详情响应。"""
    sessionId: str
    appId: str
    planId: str | None = None
    endUserId: str
    currentState: str
    currentSectionIndex: int
    messages: list[ClassroomMessageDTO] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str
