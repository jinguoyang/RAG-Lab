from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.services.knowledge_base_service import count_visible_knowledge_bases

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: CurrentUserResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> CurrentUserResponse:
    """返回当前开发用户，供前端在无生产认证时完成联调。"""
    current_user.visibleKbCount = count_visible_knowledge_bases(session, current_user)
    return current_user
