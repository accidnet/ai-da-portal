from fastapi import APIRouter

from portal_onl.api.v1.analyses import router as analyses_router
from portal_onl.api.v1.chat import router as chat_router
from portal_onl.api.v1.datasets import router as datasets_router
from portal_onl.api.v1.health import router as health_router
from portal_onl.api.v1.sessions import router as sessions_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(datasets_router, prefix="/datasets", tags=["datasets"])
api_router.include_router(analyses_router, prefix="/analyses", tags=["analyses"])
