"""外部培训应用配置。"""
import logging
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)


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

    @model_validator(mode="after")
    def _check_required_fields(self) -> "Settings":
        if not self.platform_api_key:
            logger.warning(
                "EXT_TRAINING_PLATFORM_API_KEY 未设置，平台 API 相关功能将不可用"
            )
        return self


def get_settings() -> Settings:
    return Settings()
