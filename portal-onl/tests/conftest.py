import pytest

from api.deps import (
    get_analysis_service,
    get_dataset_service,
    get_message_service,
    get_session_service,
)
from features.auth.api.deps import get_openai_auth_service, get_openai_auth_store
from infrastructure.db.base import Base
from infrastructure.db.session import engine, init_database
from main import app


@pytest.fixture(autouse=True)
def reset_state() -> None:
    app.dependency_overrides.clear()
    get_analysis_service.cache_clear()
    get_dataset_service.cache_clear()
    get_message_service.cache_clear()
    get_openai_auth_service.cache_clear()
    get_openai_auth_store.cache_clear()
    get_session_service.cache_clear()

    Base.metadata.drop_all(bind=engine)
    init_database()

    yield

    app.dependency_overrides.clear()
    get_analysis_service.cache_clear()
    get_dataset_service.cache_clear()
    get_message_service.cache_clear()
    get_openai_auth_service.cache_clear()
    get_openai_auth_store.cache_clear()
    get_session_service.cache_clear()
