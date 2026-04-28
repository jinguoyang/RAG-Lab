from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import DependencyHealthDTO, DependencyHealthResponse, HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """返回服务基础健康状态，不探测数据库或外部依赖。"""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/health/dependencies", response_model=DependencyHealthResponse)
def read_dependency_health() -> DependencyHealthResponse:
    """返回外部依赖配置健康摘要，不主动发起网络探测以避免发布检查阻塞。"""
    settings = get_settings()
    dependencies = [
        DependencyHealthDTO(
            name="postgres",
            status="configured" if settings.database_url else "missing",
            detail="RAG_LAB_DATABASE_URL 已配置" if settings.database_url else "缺少 RAG_LAB_DATABASE_URL",
        ),
        DependencyHealthDTO(
            name="object_storage",
            status="local" if settings.storage_backend == "metadata" else "configured",
            detail=f"storage_backend={settings.storage_backend}",
        ),
        DependencyHealthDTO(
            name="embedding",
            status="local" if settings.embedding_provider == "local" else "configured",
            detail=f"provider={settings.embedding_provider}",
        ),
        DependencyHealthDTO(
            name="dense_retrieval",
            status="local" if settings.dense_retrieval_provider == "local" else "configured",
            detail=f"provider={settings.dense_retrieval_provider}",
        ),
        DependencyHealthDTO(
            name="sparse_retrieval",
            status="local" if settings.sparse_retrieval_provider == "local" else "configured",
            detail=f"provider={settings.sparse_retrieval_provider}",
        ),
        DependencyHealthDTO(
            name="graph_retrieval",
            status="local" if settings.graph_retrieval_provider == "local" else "configured",
            detail=f"provider={settings.graph_retrieval_provider}",
        ),
        DependencyHealthDTO(
            name="llm",
            status="local" if settings.llm_provider == "local" else "configured",
            detail=f"provider={settings.llm_provider}",
        ),
        DependencyHealthDTO(
            name="rerank",
            status="local" if settings.rerank_provider == "identity" else "configured",
            detail=f"provider={settings.rerank_provider}",
        ),
    ]
    status = "degraded" if any(item.status == "missing" for item in dependencies) else "ok"
    return DependencyHealthResponse(status=status, dependencies=dependencies)
