import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.paths import DATA_DIR, ROOT_DIR, WORKSPACE_STORAGE_DIR


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
            "http://localhost:5174",
            "http://127.0.0.1:5174",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    )

    project_root: Path = ROOT_DIR
    data_dir: Path = DATA_DIR
    database_url: str = f"sqlite:///{(DATA_DIR / 'portal-onl.db').as_posix()}"
    storage_root: str = "storage"
    uploads_dir: str = "storage/uploads"

    # workspace settings
    workspace_storage_dir: Path = WORKSPACE_STORAGE_DIR
    workspace_storage_ttl_seconds: int = 60 * 60 * 24 * 30
    workspace_storage_cleanup_interval_seconds: int = 60 * 60 * 24 * 7

    llm_provider: str = "openai"
    llm_model: str = "gpt-5.4"
    openai_api_key: str | None = Field(default=None, repr=False)
    openai_auth_client_id: str = "app_EMoamEEZ73f0CkXaXp7hrann"
    openai_auth_issuer: str = "https://auth.openai.com"
    openai_auth_scope: str = "openid profile email offline_access"
    openai_auth_redirect_uri: str = "http://localhost:1455/auth/callback"
    openai_auth_originator: str = "portal-onl"
    openai_auth_storage_path: str = (DATA_DIR / "openai_auth.json").as_posix()
    openai_auth_pending_ttl_seconds: int = 600
    openai_codex_api_endpoint: str = "https://chatgpt.com/backend-api/codex/responses"
    llm_request_timeout_seconds: float = 180.0
    llm_stream_recovery_attempts: int = 3
    agent_include_runtime_resources: bool = True


def resolve_env_files() -> tuple[str, ...]:
    # 개발 실행에서는 .env.dev를 함께 읽어 로컬 기본값을 덮어쓴다.
    env_files: list[str] = []

    if Path(".env").is_file():
        env_files.append(".env")

    active_profile = os.getenv("PORTAL_ENV", "").strip().lower()
    if active_profile in {"dev", "development"} and Path(".env.dev").is_file():
        env_files.append(".env.dev")

    return tuple(env_files)


@lru_cache
def get_settings() -> Settings:
    env_files = resolve_env_files()
    if env_files:
        return Settings(_env_file=env_files)
    return Settings()
