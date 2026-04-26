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
