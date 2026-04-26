from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """后端运行配置，统一从默认值、环境变量和 .env 文件读取。"""

    app_name: str = "RAG-Lab API"
    app_version: str = "0.1.0"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("RAG_LAB_BACKEND_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_DATABASE_URL", "DATABASE_URL"),
    )
    dev_auth_enabled: bool = True
    dev_default_username: str = "admin"
    dev_default_security_level: str = "public"
    storage_backend: str = Field(
        default="metadata",
        validation_alias=AliasChoices("RAG_LAB_STORAGE_BACKEND", "STORAGE_BACKEND"),
    )
    storage_bucket: str = Field(
        default="rag-lab-source",
        validation_alias=AliasChoices("RAG_LAB_STORAGE_BUCKET", "STORAGE_BUCKET"),
    )
    storage_object_prefix: str = Field(
        default="dev",
        validation_alias=AliasChoices("RAG_LAB_STORAGE_OBJECT_PREFIX", "STORAGE_OBJECT_PREFIX"),
    )
    minio_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_MINIO_ENDPOINT", "MINIO_ENDPOINT"),
    )
    minio_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_MINIO_ACCESS_KEY", "MINIO_ACCESS_KEY"),
    )
    minio_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_MINIO_SECRET_KEY", "MINIO_SECRET_KEY"),
    )
    minio_secure: bool = Field(
        default=False,
        validation_alias=AliasChoices("RAG_LAB_MINIO_SECURE", "MINIO_SECURE"),
    )
    embedding_provider: str = Field(
        default="local",
        validation_alias=AliasChoices("RAG_LAB_EMBEDDING_PROVIDER", "EMBEDDING_PROVIDER"),
    )
    embedding_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_EMBEDDING_ENDPOINT", "EMBEDDING_ENDPOINT"),
    )
    embedding_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_EMBEDDING_API_KEY", "EMBEDDING_API_KEY"),
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("RAG_LAB_EMBEDDING_MODEL", "EMBEDDING_MODEL"),
    )
    dense_retrieval_provider: str = Field(
        default="local",
        validation_alias=AliasChoices("RAG_LAB_DENSE_RETRIEVAL_PROVIDER", "DENSE_RETRIEVAL_PROVIDER"),
    )
    milvus_uri: str | None = Field(default=None, validation_alias=AliasChoices("RAG_LAB_MILVUS_URI", "MILVUS_URI"))
    milvus_token: str | None = Field(default=None, validation_alias=AliasChoices("RAG_LAB_MILVUS_TOKEN", "MILVUS_TOKEN"))
    milvus_collection: str = Field(
        default="rag_chunk_embeddings",
        validation_alias=AliasChoices("RAG_LAB_MILVUS_COLLECTION", "MILVUS_COLLECTION"),
    )
    sparse_retrieval_provider: str = Field(
        default="local",
        validation_alias=AliasChoices("RAG_LAB_SPARSE_RETRIEVAL_PROVIDER", "SPARSE_RETRIEVAL_PROVIDER"),
    )
    opensearch_hosts: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_OPENSEARCH_HOSTS", "OPENSEARCH_HOSTS"),
    )
    opensearch_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_OPENSEARCH_USERNAME", "OPENSEARCH_USERNAME"),
    )
    opensearch_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_OPENSEARCH_PASSWORD", "OPENSEARCH_PASSWORD"),
    )
    opensearch_index: str = Field(
        default="rag_chunks",
        validation_alias=AliasChoices("RAG_LAB_OPENSEARCH_INDEX", "OPENSEARCH_INDEX"),
    )
    graph_retrieval_provider: str = Field(
        default="local",
        validation_alias=AliasChoices("RAG_LAB_GRAPH_RETRIEVAL_PROVIDER", "GRAPH_RETRIEVAL_PROVIDER"),
    )
    neo4j_uri: str | None = Field(default=None, validation_alias=AliasChoices("RAG_LAB_NEO4J_URI", "NEO4J_URI"))
    neo4j_username: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_NEO4J_USERNAME", "NEO4J_USERNAME"),
    )
    neo4j_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_NEO4J_PASSWORD", "NEO4J_PASSWORD"),
    )
    neo4j_database: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_NEO4J_DATABASE", "NEO4J_DATABASE"),
    )
    llm_provider: str = Field(default="local", validation_alias=AliasChoices("RAG_LAB_LLM_PROVIDER", "LLM_PROVIDER"))
    llm_endpoint: str | None = Field(default=None, validation_alias=AliasChoices("RAG_LAB_LLM_ENDPOINT", "LLM_ENDPOINT"))
    llm_api_key: str | None = Field(default=None, validation_alias=AliasChoices("RAG_LAB_LLM_API_KEY", "LLM_API_KEY"))
    llm_model: str = Field(default="local-rag-lab", validation_alias=AliasChoices("RAG_LAB_LLM_MODEL", "LLM_MODEL"))
    rerank_provider: str = Field(
        default="identity",
        validation_alias=AliasChoices("RAG_LAB_RERANK_PROVIDER", "RERANK_PROVIDER"),
    )
    rerank_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_RERANK_ENDPOINT", "RERANK_ENDPOINT"),
    )
    rerank_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("RAG_LAB_RERANK_API_KEY", "RERANK_API_KEY"),
    )
    provider_top_k: int = Field(default=5, validation_alias=AliasChoices("RAG_LAB_PROVIDER_TOP_K", "PROVIDER_TOP_K"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RAG_LAB_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """缓存配置对象，避免每次依赖注入或应用创建时重复解析环境。"""
    return Settings()
