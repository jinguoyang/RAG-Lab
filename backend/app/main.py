from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例，并集中挂载后续 API 路由。"""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="RAG-Lab 后端 API 服务",
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
