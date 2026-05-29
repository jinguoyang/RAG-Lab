from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_console_logging


configure_console_logging()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例，并集中挂载后续 API 路由。"""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="RAG-Lab 后端 API 服务",
    )
    if settings.backend_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.backend_cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-Dev-User"],
        )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
