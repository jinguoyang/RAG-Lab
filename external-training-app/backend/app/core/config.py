"""外部培训应用配置。"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./training.db"
    platform_base_url: str = "http://localhost:8000/api/v1"
    platform_app_id: str = ""
    platform_api_key: str = ""

    model_config = {"env_prefix": "EXT_TRAINING_"}


def get_settings() -> Settings:
    return Settings()
