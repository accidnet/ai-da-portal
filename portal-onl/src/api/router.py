from fastapi import APIRouter

from api.v1.auth import router as auth_router
from api.v1.chat import router as chat_router
from api.v1.datasets import router as datasets_router
from api.v1.health import router as health_router
from api.v1.sessions import router as sessions_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(datasets_router, prefix="/datasets", tags=["datasets"])
