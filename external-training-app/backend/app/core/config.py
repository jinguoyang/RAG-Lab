"""外部培训应用配置。"""
from pathlib import Path

from pydantic_settings import BaseSettings

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/external_training"
    platform_base_url: str = "http://localhost:8000/api/v1"
    platform_app_id: str = ""
    platform_api_key: str = ""

    model_config = {
        "env_prefix": "EXT_TRAINING_",
        "env_file": str(_BACKEND_ROOT / ".env"),
        "env_file_encoding": "utf-8",
    }


def get_settings() -> Settings:
    return Settings()
