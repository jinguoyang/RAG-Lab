"""课堂路由（代理平台 API）。"""
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.tables import platform_app_bindings, training_class_sessions, training_class_messages
from app.services.platform_client import PlatformClient

router = APIRouter(prefix="/classroom", tags=["classroom"])


def _get_client(db: Session) -> PlatformClient:
    row = db.execute(platform_app_bindings.select().where(platform_app_bindings.c.status == "active")).fetchone()
    if row is None:
        raise HTTPException(400, "未配置平台绑定")
    return PlatformClient(row.platform_base_url, row.platform_api_key_ref)


@router.post("/sessions", status_code=201)
def create_session(endUserId: str, planId: str | None = None, db: Session = Depends(get_db)):
    client = _get_client(db)
    binding = db.execute(platform_app_bindings.select().where(platform_app_bindings.c.status == "active")).fetchone()
    result = client.create_classroom_session(binding.platform_app_id, endUserId, planId)

    now = datetime.now(timezone.utc)
    sid = str(uuid4())
    db.execute(training_class_sessions.insert().values(
        id=sid, external_user_id=endUserId,
        platform_session_id=result["sessionId"],
        platform_plan_id=planId, current_state=result.get("currentState", "INIT"),
        created_at=now,
    ))
    db.commit()

    return {"localSessionId": sid, **result}


@router.post("/sessions/{session_id}/events")
def submit_event(session_id: str, eventType: str, payload: str = "{}", query: str | None = None, db: Session = Depends(get_db)):
    import json
    row = db.execute(training_class_sessions.select().where(training_class_sessions.c.id == session_id)).fetchone()
    if row is None:
        raise HTTPException(404, "会话不存在")

    client = _get_client(db)
    result = client.submit_classroom_event(
        row.platform_session_id, eventType, json.loads(payload), query
    )

    now = datetime.now(timezone.utc)
    db.execute(training_class_sessions.update().where(
        training_class_sessions.c.id == session_id
    ).values(current_state=result.get("classroomState", row.current_state), last_event_at=now))

    # Save message
    if result.get("visibleContent"):
        db.execute(training_class_messages.insert().values(
            id=str(uuid4()), session_id=session_id, role="assistant",
            content=result["visibleContent"],
            platform_message_id=result.get("eventId"),
            ui_actions_json=result.get("uiActions"),
            created_at=now,
        ))
    if query:
        db.execute(training_class_messages.insert().values(
            id=str(uuid4()), session_id=session_id, role="user",
            content=query, created_at=now,
        ))

    db.commit()
    return result


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    row = db.execute(training_class_sessions.select().where(training_class_sessions.c.id == session_id)).fetchone()
    if row is None:
        raise HTTPException(404, "会话不存在")

    client = _get_client(db)
    platform_data = client.get_classroom_session(row.platform_session_id)

    msgs = db.execute(
        training_class_messages.select().where(training_class_messages.c.session_id == session_id)
        .order_by(training_class_messages.c.created_at)
    ).fetchall()

    return {
        **platform_data,
        "localSessionId": session_id,
        "localMessages": [
            {"id": m.id, "role": m.role, "content": m.content, "uiActions": m.ui_actions_json}
            for m in msgs
        ],
    }
