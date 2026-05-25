from contextvars import ContextVar
from dataclasses import dataclass
import logging
from pathlib import Path

from core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkspaceFileContext:
    """agent tool이 사용할 워크스페이스 로컬 저장소 컨텍스트입니다."""

    workspace_id: str
    local_path: Path


_workspace_file_context: ContextVar[WorkspaceFileContext | None] = ContextVar(
    "workspace_file_context",
    default=None,
)


def set_workspace_file_context(
    *,
    workspace_id: str | None,
    local_path: str | None,
) -> None:
    """현재 agent 실행에서 사용할 워크스페이스 로컬 저장소를 설정합니다."""
    if workspace_id is None or local_path is None:
        logger.debug(
            "Clearing workspace file context workspace_id=%s local_path_present=%s",
            workspace_id,
            local_path is not None,
        )
        _workspace_file_context.set(None)
        return

    path = Path(local_path)
    logger.debug(
        "Setting workspace file context workspace_id=%s local_path=%s exists=%s is_dir=%s",
        workspace_id,
        path,
        path.exists(),
        path.is_dir(),
    )
    _workspace_file_context.set(
        WorkspaceFileContext(workspace_id=workspace_id, local_path=path)
    )


def clear_workspace_file_context() -> None:
    """요청 종료 시 워크스페이스 로컬 저장소 컨텍스트를 정리합니다."""
    _workspace_file_context.set(None)


def require_workspace_file_context() -> WorkspaceFileContext:
    """워크스페이스 로컬 저장소 컨텍스트를 반환하거나 명확한 오류를 발생시킵니다."""
    context = _workspace_file_context.get()
    if context is None:
        logger.warning("Workspace file context is missing for current tool execution.")
        raise ValueError("Workspace local storage is not available for this session.")
    return context


def resolve_workspace_path(relative_path: str | None) -> Path:
    """tool 입력 상대 경로를 워크스페이스 저장소 내부 절대 경로로 변환합니다."""
    context = require_workspace_file_context()
    workspace_root = context.local_path.resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    requested_path = (workspace_root / (relative_path or "")).resolve()
    if requested_path != workspace_root and workspace_root not in requested_path.parents:
        raise ValueError("Path must stay inside the workspace local storage.")
    return requested_path


def workspace_usage_payload() -> dict[str, object] | None:
    """LLM developer input에 포함할 워크스페이스 로컬 저장소 정보를 반환합니다."""
    context = _workspace_file_context.get()
    if context is None:
        return None

    settings = get_settings()
    return {
        "workspace_id": context.workspace_id,
        "local_path": str(context.local_path),
        "retention_seconds": settings.workspace_storage_ttl_seconds,
        "tools": [
            "list_workspace_files",
            "read_workspace_file",
            "write_workspace_file",
            "delete_workspace_path",
            "run_workspace_cli_command",
        ],
        "usage_note": (
            "생성한 중간 데이터, 메모, 결과 파일은 워크스페이스 로컬 저장소 내부 상대 경로로만 관리하세요. "
            "이 저장소는 주기적으로 비워질 수 있으므로 영구 보관이 필요한 결과는 최종 답변에 요약하세요."
        ),
    }
