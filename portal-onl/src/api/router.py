from fastapi import APIRouter

from api.v1.chat import router as chat_router
from api.v1.health import router as health_router
from api.v1.sessions import router as sessions_router
from features.auth.api.router import router as auth_router
from features.data_sources.api.router import router as data_sources_router
from features.datasets.api.router import router as datasets_router
from features.workspaces.api.router import router as workspaces_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(workspaces_router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(data_sources_router, prefix="/data-sources", tags=["data-sources"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(datasets_router, prefix="/datasets", tags=["datasets"])
