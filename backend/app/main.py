from fastapi import FastAPI

from app.api.router import api_router


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例，并集中挂载后续 API 路由。"""
    app = FastAPI(
        title="RAG-Lab API",
        version="0.1.0",
        description="RAG-Lab 后端 API 服务",
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
