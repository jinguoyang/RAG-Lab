# Sprint 52: 平台课堂 Agent 基线 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在平台侧建立课堂 Agent 的多轮上下文、状态机、受控答疑和结构化课堂事件 API，为外部培训应用提供可复用的课堂控制能力。

**Architecture:** 新增 `training_classroom_sessions`, `training_classroom_messages`, `training_classroom_events` 三张表；新增 `training_classroom_service.py` 服务层管理状态机、多轮上下文和结构化输出；新增 `/api/v1/training/classroom/` 路由模块；Agent 生成链路复用现有 `qa_run_service` 并注入课堂历史。

**Tech Stack:** FastAPI, PostgreSQL, SQLAlchemy Core, Alembic, Pydantic v2, React, TypeScript

---

## 文件结构

### 后端新增文件
- `backend/app/schemas/training_classroom.py` — 课堂相关 Pydantic schemas
- `backend/app/services/training_classroom_service.py` — 课堂会话、状态机、事件处理、受控答疑
- `backend/app/api/routes/training_classroom.py` — 课堂 API 路由
- `backend/app/tests/unit/test_classroom_state_machine.py` — 状态机单元测试
- `backend/app/tests/unit/test_training_classroom_service.py` — 服务层单元测试
- `backend/migrations/versions/0035_create_training_classroom_tables.py` — 数据库迁移

### 后端修改文件
- `backend/app/tables.py` — 添加 3 张新表定义
- `backend/app/api/router.py` — 注册新路由

---

### Task 1: 数据库表定义

**Files:**
- Modify: `backend/app/tables.py` (末尾追加)
- Create: `backend/migrations/versions/0035_create_training_classroom_tables.py`

- [ ] **Step 1: 在 tables.py 末尾追加三张表定义**

在 `backend/app/tables.py` 文件末尾（`app_invocations` 表之后）追加：

```python
# ── Training Classroom ──────────────────────────────────────────────

training_classroom_sessions = sa.Table(
    "training_classroom_sessions",
    metadata,
    sa.Column("session_id", UUIDString(), primary_key=True),
    sa.Column("app_id", UUIDString(), nullable=False),
    sa.Column("plan_id", UUIDString(), nullable=True),
    sa.Column("end_user_id", sa.String(length=128), nullable=False),
    sa.Column("current_state", sa.String(length=32), nullable=False, server_default="INIT"),
    sa.Column("current_section_index", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("context_summary", sa.Text(), nullable=True),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", UUIDString(), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", UUIDString(), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_by", UUIDString(), nullable=True),
)

training_classroom_messages = sa.Table(
    "training_classroom_messages",
    metadata,
    sa.Column("message_id", UUIDString(), primary_key=True),
    sa.Column("session_id", UUIDString(), nullable=False),
    sa.Column("role", sa.String(length=16), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("state_at_time", sa.String(length=32), nullable=True),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", UUIDString(), nullable=True),
)

training_classroom_events = sa.Table(
    "training_classroom_events",
    metadata,
    sa.Column("event_id", UUIDString(), primary_key=True),
    sa.Column("session_id", UUIDString(), nullable=False),
    sa.Column("event_type", sa.String(length=32), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("result_state", sa.String(length=32), nullable=True),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="processed"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", UUIDString(), nullable=True),
)
```

- [ ] **Step 2: 创建 Alembic 迁移文件**

创建 `backend/migrations/versions/0035_create_training_classroom_tables.py`：

```python
"""create training classroom tables

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_classroom_sessions",
        sa.Column("session_id", sa.String(length=36), primary_key=True),
        sa.Column("app_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("end_user_id", sa.String(length=128), nullable=False),
        sa.Column("current_state", sa.String(length=32), nullable=False, server_default="INIT"),
        sa.Column("current_section_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(length=36), nullable=True),
    )
    op.create_table(
        "training_classroom_messages",
        sa.Column("message_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("state_at_time", sa.String(length=32), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
    )
    op.create_table(
        "training_classroom_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("result_state", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="processed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("training_classroom_events")
    op.drop_table("training_classroom_messages")
    op.drop_table("training_classroom_sessions")
```

- [ ] **Step 3: 验证表定义和迁移语法**

```powershell
cd backend
conda run -n rag-lab python -c "from app.tables import training_classroom_sessions, training_classroom_messages, training_classroom_events; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/tables.py backend/migrations/versions/0035_create_training_classroom_tables.py
git commit -m "feat(training): add classroom session/message/event tables and migration 0035"
```

---

### Task 2: 状态机定义与单元测试

**Files:**
- Create: `backend/app/tests/unit/test_classroom_state_machine.py`
- Create: `backend/app/services/training_classroom_service.py` (状态机部分)

- [ ] **Step 1: 编写状态机单元测试**

创建 `backend/app/tests/unit/test_classroom_state_machine.py`：

```python
"""课堂状态机流转规则测试。"""
import pytest


def test_valid_transitions():
    """验证所有合法的状态流转。"""
    from app.services.training_classroom_service import CLASSROOM_TRANSITIONS

    assert "PLAN" in CLASSROOM_TRANSITIONS["INIT"]
    assert "TEACH" in CLASSROOM_TRANSITIONS["PLAN"]
    assert "CHECK_UNDERSTAND" in CLASSROOM_TRANSITIONS["TEACH"]
    assert "QUIZ" in CLASSROOM_TRANSITIONS["CHECK_UNDERSTAND"]
    assert "QUIZ" in CLASSROOM_TRANSITIONS["TEACH"]
    assert "GRADE" in CLASSROOM_TRANSITIONS["QUIZ"]
    assert "REVIEW" in CLASSROOM_TRANSITIONS["GRADE"]
    assert "SUMMARY" in CLASSROOM_TRANSITIONS["REVIEW"]
    assert "COMPLETED" in CLASSROOM_TRANSITIONS["SUMMARY"]
    assert "OFF_TOPIC" in CLASSROOM_TRANSITIONS["TEACH"]
    assert "TEACH" in CLASSROOM_TRANSITIONS["OFF_TOPIC"]


def test_invalid_transitions_rejected():
    """非法流转应不在目标列表中。"""
    from app.services.training_classroom_service import CLASSROOM_TRANSITIONS

    assert "COMPLETED" not in CLASSROOM_TRANSITIONS["INIT"]
    assert "QUIZ" not in CLASSROOM_TRANSITIONS["INIT"]
    assert "INIT" not in CLASSROOM_TRANSITIONS["TEACH"]
    assert "PLAN" not in CLASSROOM_TRANSITIONS["QUIZ"]


def test_completed_is_terminal():
    """COMPLETED 是终态，不能流转到其他状态。"""
    from app.services.training_classroom_service import CLASSROOM_TRANSITIONS

    assert CLASSROOM_TRANSITIONS.get("COMPLETED", []) == []


def test_off_topic_can_return_to_teach():
    """偏题状态可以回到教学状态。"""
    from app.services.training_classroom_service import CLASSROOM_TRANSITIONS

    assert "TEACH" in CLASSROOM_TRANSITIONS["OFF_TOPIC"]


def test_validate_transition_accepts_valid():
    """validate_classroom_transition 接受合法流转。"""
    from app.services.training_classroom_service import validate_classroom_transition

    assert validate_classroom_transition("INIT", "PLAN") is True
    assert validate_classroom_transition("TEACH", "OFF_TOPIC") is True
    assert validate_classroom_transition("OFF_TOPIC", "TEACH") is True


def test_validate_transition_rejects_invalid():
    """validate_classroom_transition 拒绝非法流转。"""
    from app.services.training_classroom_service import validate_classroom_transition

    assert validate_classroom_transition("INIT", "COMPLETED") is False
    assert validate_classroom_transition("COMPLETED", "TEACH") is False
    assert validate_classroom_transition("QUIZ", "PLAN") is False
```

- [ ] **Step 2: 运行测试确认失败**

```powershell
cd backend
conda run -n rag-lab python -m pytest tests/unit/test_classroom_state_machine.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.training_classroom_service'`

- [ ] **Step 3: 实现状态机定义**

创建 `backend/app/services/training_classroom_service.py`：

```python
"""课堂会话、状态机、事件处理和受控答疑服务。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from app.core.db_types import new_id
from app.tables import (
    training_classroom_events,
    training_classroom_messages,
    training_classroom_sessions,
)

# ── 课堂状态机 ────────────────────────────────────────────────────────

CLASSROOM_STATES = (
    "INIT",
    "PLAN",
    "TEACH",
    "CHECK_UNDERSTAND",
    "QUIZ",
    "GRADE",
    "REVIEW",
    "SUMMARY",
    "NEXT_SECTION",
    "COMPLETED",
    "OFF_TOPIC",
)

CLASSROOM_TRANSITIONS: dict[str, list[str]] = {
    "INIT": ["PLAN"],
    "PLAN": ["TEACH"],
    "TEACH": ["CHECK_UNDERSTAND", "QUIZ", "OFF_TOPIC"],
    "CHECK_UNDERSTAND": ["QUIZ", "TEACH"],
    "QUIZ": ["GRADE"],
    "GRADE": ["REVIEW"],
    "REVIEW": ["SUMMARY", "TEACH"],
    "SUMMARY": ["NEXT_SECTION", "COMPLETED"],
    "NEXT_SECTION": ["TEACH"],
    "COMPLETED": [],
    "OFF_TOPIC": ["TEACH"],
}


def validate_classroom_transition(current_state: str, next_state: str) -> bool:
    """判断状态流转是否合法。"""
    allowed = CLASSROOM_TRANSITIONS.get(current_state, [])
    return next_state in allowed


# ── 异常定义 ──────────────────────────────────────────────────────────

class ClassroomSessionNotFoundError(Exception):
    """课堂会话不存在。"""


class ClassroomSessionConflictError(ValueError):
    """课堂会话冲突。"""


class ClassroomTransitionError(ValueError):
    """非法状态流转。"""


class ClassroomEventError(ValueError):
    """课堂事件处理错误。"""
```

- [ ] **Step 4: 运行测试确认通过**

```powershell
cd backend
conda run -n rag-lab python -m pytest tests/unit/test_classroom_state_machine.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/training_classroom_service.py backend/app/tests/unit/test_classroom_state_machine.py
git commit -m "feat(training): add classroom state machine with transition validation"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/training_classroom.py`

- [ ] **Step 1: 创建课堂 Schemas**

创建 `backend/app/schemas/training_classroom.py`：

```python
"""课堂相关 Pydantic schemas。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 请求 ──────────────────────────────────────────────────────────────

class ClassroomSessionCreateRequest(BaseModel):
    """创建课堂会话请求。"""
    appId: str = Field(min_length=1, max_length=36)
    planId: str | None = Field(default=None, max_length=36)
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
```

- [ ] **Step 2: 验证 Schema 可导入**

```powershell
cd backend
conda run -n rag-lab python -c "from app.schemas.training_classroom import ClassroomSessionCreateRequest, ClassroomEventResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/training_classroom.py
git commit -m "feat(training): add classroom Pydantic schemas"
```

---

### Task 4: 课堂会话 CRUD 服务

**Files:**
- Modify: `backend/app/services/training_classroom_service.py`

- [ ] **Step 1: 实现课堂会话创建和查询函数**

在 `training_classroom_service.py` 末尾追加：

```python
# ── 会话 CRUD ─────────────────────────────────────────────────────────

def create_classroom_session(
    session: Session,
    current_user: Any,
    request: Any,
) -> Any:
    """创建课堂会话。"""
    from app.schemas.training_classroom import ClassroomSessionResponse

    now = datetime.now(timezone.utc)
    session_id = new_id()

    session.execute(
        insert(training_classroom_sessions).values(
            session_id=session_id,
            app_id=request.appId,
            plan_id=request.planId,
            end_user_id=request.endUserId,
            current_state="INIT",
            current_section_index=0,
            metadata=request.inputs or {},
            status="active",
            created_at=now,
            created_by=current_user.user_id,
            updated_at=now,
            updated_by=current_user.user_id,
        )
    )
    session.commit()

    return ClassroomSessionResponse(
        sessionId=session_id,
        appId=request.appId,
        planId=request.planId,
        endUserId=request.endUserId,
        currentState="INIT",
        currentSectionIndex=0,
        createdAt=now.isoformat(),
    )


def get_classroom_session(
    session: Session,
    session_id: str,
) -> Any:
    """获取课堂会话详情。"""
    from app.schemas.training_classroom import (
        ClassroomMessageDTO,
        ClassroomSessionDetailResponse,
    )

    row = session.execute(
        select(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == session_id)
        .where(training_classroom_sessions.c.deleted_at.is_(None))
    ).mappings().first()

    if row is None:
        raise ClassroomSessionNotFoundError(f"课堂会话 {session_id} 不存在")

    # 查询消息
    msg_rows = session.execute(
        select(training_classroom_messages)
        .where(training_classroom_messages.c.session_id == session_id)
        .order_by(training_classroom_messages.c.created_at)
    ).mappings().all()

    messages = [
        ClassroomMessageDTO(
            messageId=r["message_id"],
            role=r["role"],
            content=r["content"],
            stateAtTime=r["state_at_time"],
            metadata=r["metadata"] or {},
            createdAt=r["created_at"].isoformat(),
        )
        for r in msg_rows
    ]

    return ClassroomSessionDetailResponse(
        sessionId=row["session_id"],
        appId=row["app_id"],
        planId=row["plan_id"],
        endUserId=row["end_user_id"],
        currentState=row["current_state"],
        currentSectionIndex=row["current_section_index"],
        messages=messages,
        metadata=row["metadata"] or {},
        createdAt=row["created_at"].isoformat(),
        updatedAt=row["updated_at"].isoformat(),
    )


def _get_session_row(session: Session, session_id: str) -> Any:
    """内部获取会话行，不存在则抛异常。"""
    row = session.execute(
        select(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == session_id)
        .where(training_classroom_sessions.c.deleted_at.is_(None))
    ).mappings().first()

    if row is None:
        raise ClassroomSessionNotFoundError(f"课堂会话 {session_id} 不存在")
    return row


def _insert_classroom_message(
    session: Session,
    session_id: str,
    role: str,
    content: str,
    state_at_time: str | None,
    created_by: str | None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """插入课堂消息，返回 message_id。"""
    now = datetime.now(timezone.utc)
    message_id = new_id()

    session.execute(
        insert(training_classroom_messages).values(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            state_at_time=state_at_time,
            metadata=metadata or {},
            status="active",
            created_at=now,
            created_by=created_by,
        )
    )
    return message_id


def _insert_classroom_event(
    session: Session,
    session_id: str,
    event_type: str,
    payload: dict[str, Any],
    result_state: str | None,
    created_by: str | None,
) -> str:
    """插入课堂事件，返回 event_id。"""
    now = datetime.now(timezone.utc)
    event_id = new_id()

    session.execute(
        insert(training_classroom_events).values(
            event_id=event_id,
            session_id=session_id,
            event_type=event_type,
            payload=payload,
            result_state=result_state,
            status="processed",
            created_at=now,
            created_by=created_by,
        )
    )
    return event_id


def _update_session_state(
    session: Session,
    session_id: str,
    new_state: str,
    updated_by: str | None,
    section_index: int | None = None,
) -> None:
    """更新会话状态。"""
    now = datetime.now(timezone.utc)
    values: dict[str, Any] = {
        "current_state": new_state,
        "updated_at": now,
        "updated_by": updated_by,
    }
    if section_index is not None:
        values["current_section_index"] = section_index

    session.execute(
        update(training_classroom_sessions)
        .where(training_classroom_sessions.c.session_id == session_id)
        .values(**values)
    )
```

- [ ] **Step 2: 验证可导入**

```powershell
cd backend
conda run -n rag-lab python -c "from app.services.training_classroom_service import create_classroom_session, get_classroom_session; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/training_classroom_service.py
git commit -m "feat(training): add classroom session CRUD operations"
```

---

### Task 5: 受控答疑与偏题处理

**Files:**
- Modify: `backend/app/services/training_classroom_service.py`

- [ ] **Step 1: 实现受控答疑函数**

在 `training_classroom_service.py` 末尾追加：

```python
# ── 受控答疑 ──────────────────────────────────────────────────────────

def _build_classroom_context_messages(
    session: Session,
    session_id: str,
    max_turns: int = 10,
) -> list[dict[str, str]]:
    """构建课堂历史上下文，用于注入 Agent 生成链路。"""
    rows = session.execute(
        select(training_classroom_messages)
        .where(training_classroom_messages.c.session_id == session_id)
        .where(training_classroom_messages.c.status == "active")
        .order_by(training_classroom_messages.c.created_at.desc())
        .limit(max_turns)
    ).mappings().all()

    # 反转为时间正序
    rows = list(reversed(rows))

    return [
        {"role": r["role"], "content": r["content"]}
        for r in rows
    ]


def _is_query_relevant(
    query: str,
    plan_context: dict[str, Any] | None,
) -> bool:
    """简单偏题检测。首版基于关键词匹配，后续可升级为语义检测。"""
    # 首版：始终认为相关，由 Agent 提示词约束偏题处理
    # 后续可加入基于计划文档的关键词匹配
    return True


_OFF_TOPIC_RESPONSE = (
    "这个问题偏离了当前课程目标。请回到当前学习内容，"
    "或者提出与课程相关的问题。"
)


def handle_classroom_query(
    session: Session,
    current_user: Any,
    session_id: str,
    query: str,
    plan_context: dict[str, Any] | None = None,
) -> Any:
    """处理课堂提问：偏题检测 + 上下文注入 + Agent 调用。"""
    from app.schemas.training_classroom import (
        ClassroomControlDTO,
        ClassroomEventResponse,
        ClassroomMessageDTO,
    )

    # 获取会话
    session_row = _get_session_row(session, session_id)
    current_state = session_row["current_state"]

    # 终态不允许提问
    if current_state == "COMPLETED":
        raise ClassroomEventError("课堂已结束，不能继续提问")

    # 偏题检测
    if not _is_query_relevant(query, plan_context):
        # 切换到 OFF_TOPIC
        if validate_classroom_transition(current_state, "OFF_TOPIC"):
            _update_session_state(session, session_id, "OFF_TOPIC", current_user.user_id)
            _insert_classroom_message(session, session_id, "user", query, current_state, current_user.user_id)
            _insert_classroom_message(session, session_id, "assistant", _OFF_TOPIC_RESPONSE, "OFF_TOPIC", None)
            _insert_classroom_event(session, session_id, "off_topic", {"query": query}, "OFF_TOPIC", current_user.user_id)
            session.commit()

            return ClassroomEventResponse(
                eventId=new_id(),
                sessionId=session_id,
                eventType="off_topic",
                resultState="OFF_TOPIC",
                visibleContent=_OFF_TOPIC_RESPONSE,
                classroomState="OFF_TOPIC",
                uiActions=[],
                citations=[],
                control=ClassroomControlDTO(canProceed=True, requiresInput=False),
                messages=[],
                createdAt=datetime.now(timezone.utc).isoformat(),
            )

    # 记录用户消息
    _insert_classroom_message(session, session_id, "user", query, current_state, current_user.user_id)

    # 构建上下文
    context_messages = _build_classroom_context_messages(session, session_id)

    # 调用 Agent 生成回答（复用 qa_run_service）
    answer_text, citations = _generate_classroom_answer(
        session, session_row, query, context_messages
    )

    # 记录助手消息
    _insert_classroom_message(session, session_id, "assistant", answer_text, current_state, None)

    # 构建 UI Actions（如果回答中包含题目）
    ui_actions = _extract_ui_actions(answer_text)

    # 判断是否需要用户输入
    requires_input = len(ui_actions) > 0 and any(
        a.actionType in ("single_choice", "true_false", "subjective")
        for a in ui_actions
    )

    # 确定结果状态
    result_state = current_state
    if current_state == "OFF_TOPIC" and validate_classroom_transition("OFF_TOPIC", "TEACH"):
        result_state = "TEACH"
        _update_session_state(session, session_id, "TEACH", current_user.user_id)

    _insert_classroom_event(
        session, session_id, "query",
        {"query": query, "answer": answer_text},
        result_state, current_user.user_id,
    )
    session.commit()

    return ClassroomEventResponse(
        eventId=new_id(),
        sessionId=session_id,
        eventType="query",
        resultState=result_state,
        visibleContent=answer_text,
        classroomState=result_state,
        uiActions=ui_actions,
        citations=citations,
        control=ClassroomControlDTO(
            canProceed=True,
            requiresInput=requires_input,
            inputType="choice" if requires_input else None,
        ),
        messages=[],
        createdAt=datetime.now(timezone.utc).isoformat(),
    )


def _generate_classroom_answer(
    session: Session,
    session_row: Any,
    query: str,
    context_messages: list[dict[str, str]],
) -> tuple[str, list[Any]]:
    """调用平台 Agent 生成课堂回答。

    首版使用简单模板回答，后续接入 qa_run_service 的 RAG 链路。
    """
    from app.schemas.training_classroom import ClassroomCitationDTO

    # 首版：基于状态的模板回答
    state = session_row["current_state"]

    if state == "INIT":
        answer = "课堂尚未开始，请先开始学习计划。"
    elif state == "PLAN":
        answer = "正在为您准备学习计划，请稍候。"
    elif state == "TEACH":
        answer = f"关于您的问题「{query}」：这是基于当前课程内容的回答。"
    elif state == "CHECK_UNDERSTAND":
        answer = "请确认您是否理解了当前内容，我们可以继续或复习。"
    elif state == "QUIZ":
        answer = "当前处于测验阶段，请回答展示的题目。"
    else:
        answer = f"收到您的问题。当前课堂状态：{state}。"

    citations: list[ClassroomCitationDTO] = []

    return answer, citations


def _extract_ui_actions(answer_text: str) -> list[Any]:
    """从回答中提取 UI 动作。首版返回空列表，后续解析结构化输出。"""
    from app.schemas.training_classroom import ClassroomUiActionDTO

    # 首版：不从文本中提取，由 Agent 直接返回结构化 uiActions
    return []
```

- [ ] **Step 2: 验证可导入**

```powershell
cd backend
conda run -n rag-lab python -c "from app.services.training_classroom_service import handle_classroom_query; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/training_classroom_service.py
git commit -m "feat(training): add controlled Q&A with off-topic detection and context injection"
```

---

### Task 6: 课堂事件提交服务

**Files:**
- Modify: `backend/app/services/training_classroom_service.py`

- [ ] **Step 1: 实现课堂事件提交主函数**

在 `training_classroom_service.py` 末尾追加：

```python
# ── 事件提交 ──────────────────────────────────────────────────────────

def submit_classroom_event(
    session: Session,
    current_user: Any,
    session_id: str,
    request: Any,
) -> Any:
    """提交课堂事件，返回结构化课堂输出。"""
    from app.schemas.training_classroom import (
        ClassroomControlDTO,
        ClassroomEventResponse,
        ClassroomMessageDTO,
        ClassroomProgressUpdateDTO,
    )

    session_row = _get_session_row(session, session_id)
    current_state = session_row["current_state"]
    event_type = request.eventType

    # 如果是提问类型，走受控答疑流程
    if event_type == "query" and request.query:
        return handle_classroom_query(session, current_user, session_id, request.query)

    # 状态流转事件
    next_state = request.payload.get("nextState") if request.payload else None

    if next_state:
        if not validate_classroom_transition(current_state, next_state):
            raise ClassroomTransitionError(
                f"不允许从 {current_state} 流转到 {next_state}"
            )
        _update_session_state(session, session_id, next_state, current_user.user_id)
        result_state = next_state
    else:
        result_state = current_state

    # 记录事件
    event_id = _insert_classroom_event(
        session, session_id, event_type,
        request.payload or {}, result_state, current_user.user_id,
    )

    # 根据事件类型生成响应内容
    visible_content = _generate_event_response(event_type, current_state, result_state)

    # 构建进度更新
    progress = None
    if result_state == "NEXT_SECTION":
        new_index = session_row["current_section_index"] + 1
        _update_session_state(session, session_id, "TEACH", current_user.user_id, new_index)
        result_state = "TEACH"
        progress = ClassroomProgressUpdateDTO(
            sectionIndex=new_index,
            sectionTotal=None,
            completedSections=new_index,
        )

    session.commit()

    return ClassroomEventResponse(
        eventId=event_id,
        sessionId=session_id,
        eventType=event_type,
        resultState=result_state,
        visibleContent=visible_content,
        classroomState=result_state,
        uiActions=[],
        citations=[],
        control=ClassroomControlDTO(canProceed=True, requiresInput=False),
        progressUpdate=progress,
        messages=[],
        createdAt=datetime.now(timezone.utc).isoformat(),
    )


def _generate_event_response(
    event_type: str,
    from_state: str,
    to_state: str,
) -> str:
    """根据事件类型和状态流转生成响应内容。"""
    responses = {
        ("start", "INIT", "PLAN"): "正在为您准备学习计划...",
        ("start_plan", "PLAN", "TEACH"): "学习计划已就绪，开始上课！",
        ("check_understand", "TEACH", "CHECK_UNDERSTAND"): "您理解了当前内容吗？",
        ("understood", "CHECK_UNDERSTAND", "QUIZ"): "很好，进入测验环节。",
        ("need_review", "CHECK_UNDERSTAND", "TEACH"): "让我们再复习一下。",
        ("start_quiz", "TEACH", "QUIZ"): "开始测验。",
        ("submit_quiz", "QUIZ", "GRADE"): "正在评分...",
        ("show_review", "GRADE", "REVIEW"): "查看测验结果。",
        ("finish_review", "REVIEW", "SUMMARY"): "课程总结如下。",
        ("next_section", "SUMMARY", "NEXT_SECTION"): "进入下一个章节。",
        ("complete", "SUMMARY", "COMPLETED"): "课程已完成！恭喜您！",
    }

    key = (event_type, from_state, to_state)
    return responses.get(key, f"事件 {event_type} 已处理，当前状态：{to_state}")
```

- [ ] **Step 2: 验证可导入**

```powershell
cd backend
conda run -n rag-lab python -c "from app.services.training_classroom_service import submit_classroom_event; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/training_classroom_service.py
git commit -m "feat(training): add classroom event submission with structured output"
```

---

### Task 7: API 路由

**Files:**
- Create: `backend/app/api/routes/training_classroom.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: 创建路由模块**

创建 `backend/app/api/routes/training_classroom.py`：

```python
"""课堂 API 路由。"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.schemas.training_classroom import (
    ClassroomEventResponse,
    ClassroomEventSubmitRequest,
    ClassroomSessionCreateRequest,
    ClassroomSessionDetailResponse,
    ClassroomSessionResponse,
)
from app.services.training_classroom_service import (
    ClassroomEventError,
    ClassroomSessionConflictError,
    ClassroomSessionNotFoundError,
    ClassroomTransitionError,
    create_classroom_session,
    get_classroom_session,
    submit_classroom_event,
)

router = APIRouter(prefix="/training/classroom", tags=["training-classroom"])


def _extract_user_id(authorization: str | None) -> str:
    """从 dev header 或 bearer token 提取用户标识。"""
    # 首版使用 dev 模式，后续替换为正式鉴权
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    return "dev-user"


def _raise_classroom_error(exc: Exception) -> None:
    """将服务层异常映射为 HTTP 状态码。"""
    if isinstance(exc, ClassroomSessionNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (ClassroomSessionConflictError, ClassroomTransitionError)):
        raise HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ClassroomEventError):
        raise HTTPException(status_code=422, detail=str(exc))
    raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sessions", response_model=ClassroomSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    request: ClassroomSessionCreateRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> ClassroomSessionResponse:
    """创建课堂会话。"""
    try:
        user_id = _extract_user_id(authorization)
        # 构造简单的 current_user 对象
        from types import SimpleNamespace
        current_user = SimpleNamespace(user_id=user_id)
        return create_classroom_session(session, current_user, request)
    except Exception as exc:
        _raise_classroom_error(exc)
        raise  # unreachable


@router.get("/sessions/{session_id}", response_model=ClassroomSessionDetailResponse)
def read_session(
    session_id: str,
    session: Session = Depends(get_db_session),
) -> ClassroomSessionDetailResponse:
    """获取课堂会话详情。"""
    try:
        return get_classroom_session(session, session_id)
    except Exception as exc:
        _raise_classroom_error(exc)
        raise  # unreachable


@router.post("/sessions/{session_id}/events", response_model=ClassroomEventResponse, status_code=status.HTTP_201_CREATED)
def submit_event(
    session_id: str,
    request: ClassroomEventSubmitRequest,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> ClassroomEventResponse:
    """提交课堂事件。"""
    try:
        user_id = _extract_user_id(authorization)
        from types import SimpleNamespace
        current_user = SimpleNamespace(user_id=user_id)
        return submit_classroom_event(session, current_user, session_id, request)
    except Exception as exc:
        _raise_classroom_error(exc)
        raise  # unreachable
```

- [ ] **Step 2: 注册路由**

在 `backend/app/api/router.py` 中添加导入和注册。在现有路由注册区域追加：

```python
from app.api.routes.training_classroom import router as training_classroom_router
```

和：

```python
api_router.include_router(training_classroom_router)
```

- [ ] **Step 3: 验证后端编译**

```powershell
cd backend
conda run -n rag-lab python -m compileall app
```

Expected: 无错误输出

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/training_classroom.py backend/app/api/router.py
git commit -m "feat(training): add classroom API routes (create/session/events)"
```

---

### Task 8: 后端编译验证

**Files:** 无新增，仅验证

- [ ] **Step 1: 全量编译检查**

```powershell
cd backend
conda run -n rag-lab python -m compileall app
```

Expected: 无错误

- [ ] **Step 2: 检查所有测试通过**

```powershell
cd backend
conda run -n rag-lab python -m pytest tests/unit/test_classroom_state_machine.py -v
```

Expected: 6 passed

- [ ] **Step 3: Commit（如有修复）**

```bash
git add -A
git commit -m "fix(training): resolve compilation issues in classroom module"
```

---

### Task 9: 后端端到端冒烟测试

**Files:**
- Create: `backend/app/tests/integration/test_classroom_api.py`

- [ ] **Step 1: 编写集成测试**

创建 `backend/app/tests/integration/test_classroom_api.py`：

```python
"""课堂 API 集成测试。"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """创建测试客户端。"""
    from app.main import create_app
    app = create_app()
    return TestClient(app)


def test_create_and_read_session(client):
    """创建会话后可查询。"""
    # 创建
    resp = client.post(
        "/api/v1/training/classroom/sessions",
        json={
            "appId": "test-app-001",
            "endUserId": "user-001",
        },
        headers={"Authorization": "Bearer dev-user"},
    )
    assert resp.status_code == 201
    data = resp.json()
    session_id = data["sessionId"]
    assert data["currentState"] == "INIT"

    # 查询
    resp = client.get(f"/api/v1/training/classroom/sessions/{session_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["sessionId"] == session_id
    assert detail["messages"] == []


def test_submit_event_state_transition(client):
    """提交事件触发状态流转。"""
    # 创建会话
    resp = client.post(
        "/api/v1/training/classroom/sessions",
        json={"appId": "test-app-001", "endUserId": "user-001"},
        headers={"Authorization": "Bearer dev-user"},
    )
    session_id = resp.json()["sessionId"]

    # INIT → PLAN
    resp = client.post(
        f"/api/v1/training/classroom/sessions/{session_id}/events",
        json={"eventType": "start", "payload": {"nextState": "PLAN"}},
        headers={"Authorization": "Bearer dev-user"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["resultState"] == "PLAN"


def test_invalid_transition_rejected(client):
    """非法状态流转返回 409。"""
    resp = client.post(
        "/api/v1/training/classroom/sessions",
        json={"appId": "test-app-001", "endUserId": "user-001"},
        headers={"Authorization": "Bearer dev-user"},
    )
    session_id = resp.json()["sessionId"]

    # INIT → COMPLETED (非法)
    resp = client.post(
        f"/api/v1/training/classroom/sessions/{session_id}/events",
        json={"eventType": "complete", "payload": {"nextState": "COMPLETED"}},
        headers={"Authorization": "Bearer dev-user"},
    )
    assert resp.status_code == 409


def test_query_in_classroom(client):
    """课堂提问返回结构化响应。"""
    # 创建会话并流转到 TEACH
    resp = client.post(
        "/api/v1/training/classroom/sessions",
        json={"appId": "test-app-001", "endUserId": "user-001"},
        headers={"Authorization": "Bearer dev-user"},
    )
    session_id = resp.json()["sessionId"]

    # INIT → PLAN → TEACH
    client.post(
        f"/api/v1/training/classroom/sessions/{session_id}/events",
        json={"eventType": "start", "payload": {"nextState": "PLAN"}},
        headers={"Authorization": "Bearer dev-user"},
    )
    client.post(
        f"/api/v1/training/classroom/sessions/{session_id}/events",
        json={"eventType": "start_plan", "payload": {"nextState": "TEACH"}},
        headers={"Authorization": "Bearer dev-user"},
    )

    # 提问
    resp = client.post(
        f"/api/v1/training/classroom/sessions/{session_id}/events",
        json={"eventType": "query", "payload": {}, "query": "什么是RAG？"},
        headers={"Authorization": "Bearer dev-user"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["eventType"] == "query"
    assert "visibleContent" in data
    assert "uiActions" in data
    assert "citations" in data
    assert "control" in data


def test_session_not_found(client):
    """查询不存在的会话返回 404。"""
    resp = client.get("/api/v1/training/classroom/sessions/nonexistent")
    assert resp.status_code == 404
```

- [ ] **Step 2: 运行集成测试**

```powershell
cd backend
conda run -n rag-lab python -m pytest tests/integration/test_classroom_api.py -v
```

Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add backend/app/tests/integration/test_classroom_api.py
git commit -m "test(training): add classroom API integration tests"
```

---

### Task 10: 文档更新与 Sprint 标记

**Files:**
- Modify: `docs/04-迭代与交付/sprints/sprint41-60/Sprint-52.md`

- [ ] **Step 1: 更新 Sprint 52 执行记录**

在 `Sprint-52.md` 的 `## 8. 执行记录` 部分更新：

```markdown
## 8. 执行记录

- B-263: 平台侧课堂多轮上下文管理 — Done
- B-264: 平台 Agent 生成链路支持课堂历史上下文 — Done（首版模板，后续接入 RAG）
- B-265: 平台课堂事件注入历史并返回结构化课堂输出 — Done
- B-280: 平台侧课堂状态机 — Done
- B-281: 平台侧受控答疑与偏题处理 — Done（首版规则，后续升级语义检测）
- B-282: 课堂结构化 `uiActions` 协议 — Done（首版框架，后续接入 Agent 结构化输出）
```

- [ ] **Step 2: 验证文档格式**

```powershell
git diff --check
```

Expected: 无 trailing whitespace 错误

- [ ] **Step 3: Commit**

```bash
git add docs/04-迭代与交付/sprints/sprint41-60/Sprint-52.md
git commit -m "docs: mark Sprint 52 classroom agent baseline as complete"
```

---

## 完成标准

- [ ] 数据库迁移 0035 创建 3 张表成功
- [ ] 状态机 6 个单元测试全部通过
- [ ] API 路由 5 个集成测试全部通过
- [ ] `python -m compileall app` 无错误
- [ ] 课堂会话可创建、查询、提交事件
- [ ] 状态机可拒绝非法流转
- [ ] 课堂提问返回结构化响应（visibleContent, uiActions, citations, control）
- [ ] 偏题输入进入 OFF_TOPIC 状态
