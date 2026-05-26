"""平台绑定路由。"""
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.binding import BindingCreateRequest, BindingResponse
from app.tables import platform_app_bindings

router = APIRouter(prefix="/bindings", tags=["bindings"])


@router.post("", response_model=BindingResponse, status_code=201)
def create_binding(request: BindingCreateRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    binding_id = str(uuid4())
    db.execute(platform_app_bindings.insert().values(
        id=binding_id, platform_base_url=request.platformBaseUrl,
        platform_app_id=request.platformAppId, platform_api_key_ref=request.platformApiKey,
        status="active", created_at=now,
    ))
    db.commit()
    return BindingResponse(id=binding_id, platformBaseUrl=request.platformBaseUrl,
                          platformAppId=request.platformAppId, status="active", createdAt=now.isoformat())


@router.get("", response_model=list[BindingResponse])
def list_bindings(db: Session = Depends(get_db)):
    rows = db.execute(platform_app_bindings.select().where(platform_app_bindings.c.status == "active")).fetchall()
    return [BindingResponse(id=r.id, platformBaseUrl=r.platform_base_url,
                           platformAppId=r.platform_app_id, status=r.status,
                           createdAt=r.created_at.isoformat()) for r in rows]
