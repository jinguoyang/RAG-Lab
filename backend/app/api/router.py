from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
"""API 路由聚合器；后续模块路由统一在这里注册。"""

api_router.include_router(auth_router)
api_router.include_router(health_router)
