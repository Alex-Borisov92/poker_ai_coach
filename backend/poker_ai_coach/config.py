from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_runtime_hm3_db_path: Path | None = None


class Settings(BaseSettings):
    hm3_db_path: Path | None = Field(default=None, alias="HM3_DB_PATH")
    hero_name: str = Field(default="surok_valera", alias="HERO_NAME")
    ai_enabled: bool = Field(default=False, alias="AI_ENABLED")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str | None = Field(default=None, alias="OPENAI_MODEL")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings:
    settings = Settings()
    if _runtime_hm3_db_path is not None:
        settings.hm3_db_path = _runtime_hm3_db_path
    return settings


def set_runtime_hm3_db_path(database_path: Path) -> None:
    global _runtime_hm3_db_path
    _runtime_hm3_db_path = database_path


def clear_runtime_hm3_db_path() -> None:
    global _runtime_hm3_db_path
    _runtime_hm3_db_path = None
