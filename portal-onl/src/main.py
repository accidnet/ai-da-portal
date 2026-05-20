import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router
from core.config import get_settings
from core.logging import configure_logging
from features.workspaces.application.cleanup import (
    cancel_cleanup_task,
    cleanup_workspace_storage_once,
    run_workspace_storage_cleanup_loop,
    wait_cleanup_task_cancelled,
)
from features.workspaces.application.local_storage import WorkspaceLocalStorage
from infrastructure.db.session import init_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    init_database()
    settings = get_settings()
    workspace_local_storage = WorkspaceLocalStorage(
        root_dir=settings.workspace_storage_dir,
        ttl_seconds=settings.workspace_storage_ttl_seconds,
    )
    # 서버 시작 시 이전 실행에서 만료된 워크스페이스 로컬 공간을 먼저 정리합니다.
    cleanup_workspace_storage_once(workspace_local_storage)
    # 서버 실행 중에는 설정된 주기마다 만료된 워크스페이스 로컬 공간을 백그라운드에서 정리합니다.
    cleanup_task = asyncio.create_task(
        run_workspace_storage_cleanup_loop(
            local_storage=workspace_local_storage,
            settings=settings,
        )
    )
    try:
        yield
    finally:
        # 앱 종료 시 백그라운드 정리 task를 남기지 않고 종료합니다.
        cancel_cleanup_task(cleanup_task)
        await wait_cleanup_task_cancelled(cleanup_task)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=f"{settings.api_v1_prefix}/docs",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        # settings 로그 레벨을 uvicorn 실행 로그에도 동일하게 적용한다.
        log_level=settings.log_level.lower(),
        factory=False,
        app_dir="src",
    )


if __name__ == "__main__":
    main()
