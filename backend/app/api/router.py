from fastapi import APIRouter

from app.api.routes.agent_scenarios import router as agent_scenarios_router
from app.api.routes.audit_logs import router as audit_logs_router
from app.api.routes.app_runtime import router as app_runtime_router
from app.api.routes.auth import router as auth_router
from app.api.routes.config import revision_router as config_revision_router
from app.api.routes.config import template_router as config_template_router
from app.api.routes.config import effectiveness_router as config_effectiveness_router
from app.api.routes.parser_routing import router as parser_routing_router
from app.api.routes.dictionaries import router as dictionaries_router
from app.api.routes.documents import chunk_router, index_sync_router, ingest_job_router, router as documents_router
from app.api.routes.graph import router as graph_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_bases import router as knowledge_bases_router
from app.api.routes.library import router as library_router
from app.api.routes.library_management import router as library_management_router
from app.api.routes.bindings import router as bindings_router
from app.api.routes.observability import router as observability_router
from app.api.routes.qa_runs import router as qa_runs_router
from app.api.routes.rag_apps import router as rag_apps_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.training_plans import router as training_plans_router
from app.api.routes.training_questions import router as training_questions_router
from app.api.routes.training_classroom import router as training_classroom_router
from app.api.routes.training_reports import router as training_reports_router
from app.api.routes.training_documents import router as training_documents_router
from app.api.routes.training_post_quizzes import router as training_post_quizzes_router
from app.api.routes.users_groups import groups_router, users_router

api_router = APIRouter()
"""API 路由聚合器；后续模块路由统一在这里注册。"""

api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(agent_scenarios_router)
api_router.include_router(audit_logs_router)
api_router.include_router(dictionaries_router)
api_router.include_router(users_router)
api_router.include_router(groups_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(observability_router)
api_router.include_router(documents_router)
api_router.include_router(ingest_job_router)
api_router.include_router(chunk_router)
api_router.include_router(index_sync_router)
api_router.include_router(config_template_router)
api_router.include_router(config_revision_router)
api_router.include_router(config_effectiveness_router)
api_router.include_router(parser_routing_router)
api_router.include_router(qa_runs_router)
api_router.include_router(graph_router)
api_router.include_router(rag_apps_router)
api_router.include_router(tasks_router)
api_router.include_router(app_runtime_router)
api_router.include_router(library_router)
api_router.include_router(library_management_router)
api_router.include_router(bindings_router)
api_router.include_router(training_plans_router)
api_router.include_router(training_documents_router)
api_router.include_router(training_questions_router)
api_router.include_router(training_post_quizzes_router)
api_router.include_router(training_classroom_router)
api_router.include_router(training_reports_router)

from app.core.config import get_settings

if get_settings().test_seed_enabled:
    from app.api.routes.test_seed import router as test_seed_router

    api_router.include_router(test_seed_router)
