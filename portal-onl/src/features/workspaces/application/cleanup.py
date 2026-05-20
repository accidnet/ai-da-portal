import asyncio
import logging
from contextlib import suppress

from core.config import Settings
from features.workspaces.application.local_storage import WorkspaceLocalStorage

logger = logging.getLogger(__name__)


async def run_workspace_storage_cleanup_loop(
    *,
    local_storage: WorkspaceLocalStorage,
    settings: Settings,
) -> None:
    """설정된 주기마다 만료된 워크스페이스 로컬 저장소를 제거합니다."""
    interval_seconds = max(settings.workspace_storage_cleanup_interval_seconds, 60)
    while True:
        await asyncio.sleep(interval_seconds)
        _cleanup_expired(local_storage)


def cleanup_workspace_storage_once(local_storage: WorkspaceLocalStorage) -> None:
    """앱 시작 시 만료된 워크스페이스 로컬 저장소를 1회 정리합니다."""
    _cleanup_expired(local_storage)


def cancel_cleanup_task(task: asyncio.Task[None]) -> None:
    """FastAPI 종료 시 백그라운드 정리 task를 취소합니다."""
    task.cancel()


async def wait_cleanup_task_cancelled(task: asyncio.Task[None]) -> None:
    """취소된 백그라운드 정리 task가 종료될 때까지 대기합니다."""
    with suppress(asyncio.CancelledError):
        await task


def _cleanup_expired(local_storage: WorkspaceLocalStorage) -> None:
    """만료 정리 결과를 로그로 남깁니다."""
    removed_workspace_ids = local_storage.cleanup_expired()
    if removed_workspace_ids:
        logger.info(
            "Removed expired workspace local storage count=%s workspace_ids=%s",
            len(removed_workspace_ids),
            removed_workspace_ids,
        )
