from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI

from portal_onl.api.router import api_router
from portal_onl.core.config import get_settings
from portal_onl.core.logging import configure_logging


@contextmanager
def lifespan(_: FastAPI) -> Iterator[None]:
    configure_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url=f"{settings.api_v1_prefix}/docs",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "portal_onl.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        factory=False,
    )


if __name__ == "__main__":
    main()
