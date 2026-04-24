from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.schemas.auth import CurrentUserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=CurrentUserResponse)
def read_current_user(
    current_user: CurrentUserResponse = Depends(get_current_user),
) -> CurrentUserResponse:
    """返回当前开发用户，供前端在无生产认证时完成联调。"""
    return current_user
