from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import DependencyConfigItemDTO, DependencyHealthDTO, DependencyHealthResponse, HealthResponse

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


def _sanitize_display_value(value: str | None, sensitive: bool) -> str | None:
    """生成安全展示值；敏感值只显示占位，URL 类配置移除查询参数。"""
    if value is None or value == "":
        return None
    if sensitive:
        return "***redacted***"
    return value.split("?", 1)[0]


def _config_item(key: str, value: str | None, sensitive: bool = False, required: bool = True) -> DependencyConfigItemDTO:
    """构造单个配置项检查结果，避免健康检查响应泄露密钥。"""
    configured = value is not None and value != ""
    return DependencyConfigItemDTO(
        key=key,
        status="configured" if configured else ("missing" if required else "optional"),
        displayValue=_sanitize_display_value(value, sensitive),
        sensitive=sensitive,
    )


def _dependency(
    name: str,
    provider: str | None,
    config: list[DependencyConfigItemDTO],
    local_providers: set[str],
) -> DependencyHealthDTO:
    """根据 Provider 类型和必填配置项计算本地配置健康状态。"""
    if provider in local_providers:
        return DependencyHealthDTO(
            name=name,
            provider=provider,
            status="local",
            detail=f"provider={provider} 使用本地降级能力",
            config=config,
        )

    missing_keys = [item.key for item in config if item.status == "missing"]
    if missing_keys:
        return DependencyHealthDTO(
            name=name,
            provider=provider,
            status="missing",
            detail=f"缺少必填配置: {', '.join(missing_keys)}",
            config=config,
        )
    return DependencyHealthDTO(
        name=name,
        provider=provider,
        status="configured",
        detail=f"provider={provider} 已完成本地配置校验",
        config=config,
    )


@router.get("/health/dependencies", response_model=DependencyHealthResponse)
def read_dependency_health() -> DependencyHealthResponse:
    """返回外部依赖配置健康摘要，不主动发起网络探测以避免发布检查阻塞。"""
    settings = get_settings()
    dependencies = [
        _dependency(
            name="postgres",
            provider="postgres",
            local_providers=set(),
            config=[_config_item("RAG_LAB_DATABASE_URL", settings.database_url, sensitive=True)],
        ),
        _dependency(
            name="object_storage",
            provider=settings.storage_backend,
            local_providers={"metadata"},
            config=[
                _config_item("RAG_LAB_STORAGE_BUCKET", settings.storage_bucket),
                _config_item("RAG_LAB_STORAGE_OBJECT_PREFIX", settings.storage_object_prefix, required=False),
                _config_item("RAG_LAB_MINIO_ENDPOINT", settings.minio_endpoint),
                _config_item("RAG_LAB_MINIO_ACCESS_KEY", settings.minio_access_key, sensitive=True),
                _config_item("RAG_LAB_MINIO_SECRET_KEY", settings.minio_secret_key, sensitive=True),
            ],
        ),
        _dependency(
            name="embedding",
            provider=settings.embedding_provider,
            local_providers={"local"},
            config=[
                _config_item("RAG_LAB_EMBEDDING_ENDPOINT", settings.embedding_endpoint),
                _config_item("RAG_LAB_EMBEDDING_API_KEY", settings.embedding_api_key, sensitive=True),
                _config_item("RAG_LAB_EMBEDDING_MODEL", settings.embedding_model),
            ],
        ),
        _dependency(
            name="dense_retrieval",
            provider=settings.dense_retrieval_provider,
            local_providers={"local"},
            config=[
                _config_item("RAG_LAB_MILVUS_URI", settings.milvus_uri),
                _config_item("RAG_LAB_MILVUS_TOKEN", settings.milvus_token, sensitive=True, required=False),
                _config_item("RAG_LAB_MILVUS_COLLECTION", settings.milvus_collection),
            ],
        ),
        _dependency(
            name="sparse_retrieval",
            provider=settings.sparse_retrieval_provider,
            local_providers={"local"},
            config=[
                _config_item("RAG_LAB_OPENSEARCH_HOSTS", settings.opensearch_hosts),
                _config_item("RAG_LAB_OPENSEARCH_USERNAME", settings.opensearch_username),
                _config_item("RAG_LAB_OPENSEARCH_PASSWORD", settings.opensearch_password, sensitive=True),
                _config_item("RAG_LAB_OPENSEARCH_INDEX", settings.opensearch_index),
            ],
        ),
        _dependency(
            name="graph_retrieval",
            provider=settings.graph_retrieval_provider,
            local_providers={"local"},
            config=[
                _config_item("RAG_LAB_NEO4J_URI", settings.neo4j_uri),
                _config_item("RAG_LAB_NEO4J_USERNAME", settings.neo4j_username),
                _config_item("RAG_LAB_NEO4J_PASSWORD", settings.neo4j_password, sensitive=True),
                _config_item("RAG_LAB_NEO4J_DATABASE", settings.neo4j_database, required=False),
            ],
        ),
        _dependency(
            name="llm",
            provider=settings.llm_provider,
            local_providers={"local"},
            config=[
                _config_item("RAG_LAB_LLM_ENDPOINT", settings.llm_endpoint),
                _config_item("RAG_LAB_LLM_API_KEY", settings.llm_api_key, sensitive=True),
                _config_item("RAG_LAB_LLM_MODEL", settings.llm_model),
            ],
        ),
        _dependency(
            name="rerank",
            provider=settings.rerank_provider,
            local_providers={"identity"},
            config=[
                _config_item("RAG_LAB_RERANK_ENDPOINT", settings.rerank_endpoint),
                _config_item("RAG_LAB_RERANK_API_KEY", settings.rerank_api_key, sensitive=True),
            ],
        ),
    ]
    status = "degraded" if any(item.status == "missing" for item in dependencies) else "ok"
    return DependencyHealthResponse(status=status, dependencies=dependencies)
