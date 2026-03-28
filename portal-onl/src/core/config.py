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
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    database_url: str = "sqlite:///./db"
    storage_root: str = "storage"
    uploads_dir: str = "storage/uploads"

    llm_provider: str = "openai"
    llm_model: str = "gpt-5.4"
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_auth_client_id: str = "app_EMoamEEZ73f0CkXaXp7hrann"
    openai_auth_issuer: str = "https://auth.openai.com"
    openai_auth_scope: str = "openid profile email offline_access"
    openai_auth_redirect_uri: str = "http://localhost:1455/auth/callback"
    openai_auth_originator: str = "portal-onl"
    openai_auth_storage_path: str = "storage/openai_auth.json"
    openai_auth_pending_ttl_seconds: int = 600
    openai_codex_api_endpoint: str = "https://chatgpt.com/backend-api/codex/responses"


@lru_cache
def get_settings() -> Settings:
    return Settings()
