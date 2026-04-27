from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.config import revision_router as config_revision_router
from app.api.routes.config import template_router as config_template_router
from app.api.routes.documents import ingest_job_router, router as documents_router
from app.api.routes.graph import router as graph_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_bases import router as knowledge_bases_router
from app.api.routes.qa_runs import router as qa_runs_router
from app.api.routes.users_groups import groups_router, users_router

api_router = APIRouter()
"""API 路由聚合器；后续模块路由统一在这里注册。"""

api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(users_router)
api_router.include_router(groups_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(documents_router)
api_router.include_router(ingest_job_router)
api_router.include_router(config_template_router)
api_router.include_router(config_revision_router)
api_router.include_router(qa_runs_router)
api_router.include_router(graph_router)
