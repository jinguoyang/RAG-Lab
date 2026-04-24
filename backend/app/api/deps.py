from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.schemas.auth import CurrentUserResponse
from app.services.dev_auth_service import get_dev_user


def get_current_user(
    x_dev_user: Annotated[str | None, Header(alias="X-Dev-User")] = None,
) -> CurrentUserResponse:
    """获取当前开发用户；生产级认证会在后续 Sprint 替换这里。"""
    settings = get_settings()
    if not settings.dev_auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development authentication is disabled.",
        )

    username = x_dev_user or settings.dev_default_username
    current_user = get_dev_user(username=username, settings=settings)
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unknown development user: {username}",
        )
    return current_user
