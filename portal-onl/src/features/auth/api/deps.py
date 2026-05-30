from functools import lru_cache

from core.config import get_settings
from features.auth.application.service import OpenAiAuthService
from features.auth.infrastructure.store import OpenAiAuthStore


@lru_cache
def get_openai_auth_store() -> OpenAiAuthStore:
    """OpenAI 인증 feature 전용 store dependency를 반환합니다."""
    settings = get_settings()
    return OpenAiAuthStore(settings.openai_auth_storage_path)


@lru_cache
def get_openai_auth_service() -> OpenAiAuthService:
    """OpenAI 인증 feature 전용 service dependency를 반환합니다."""
    return OpenAiAuthService(settings=get_settings(), store=get_openai_auth_store())
