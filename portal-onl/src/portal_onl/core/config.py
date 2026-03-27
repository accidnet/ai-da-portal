from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Portal Data Analysis AI"
    app_version: str = "0.1.0"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    log_level: str = "INFO"

    database_url: str = "sqlite:///./portal_onl.db"
    storage_root: str = "storage"
    uploads_dir: str = "storage/uploads"

    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1"
    openai_api_key: str | None = Field(default=None, repr=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
