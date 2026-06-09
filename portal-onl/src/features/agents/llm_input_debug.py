import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from core.paths import LOG_DIR

logger = logging.getLogger(__name__)
LLM_INPUT_LOG_DIR = LOG_DIR / "llm-inputs"
_SAFE_PATH_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


class LlmInputDebugContext(TypedDict, total=False):
    """LLM input debug 파일명을 구성하는 요청 식별자입니다."""

    event: str | None
    session_id: str | None
    user_message_id: str | None
    agent_run_id: str | None
    iteration: int | None


def write_llm_input_debug_file(
    *,
    context: LlmInputDebugContext,
    payload: dict[str, object],
) -> Path | None:
    """LLM 호출별 input debug payload를 조회하기 쉬운 JSON 파일로 저장합니다."""
    try:
        now = datetime.now(UTC)
        session_id = _safe_part(context.get("session_id"), fallback="unknown-session")
        log_dir = LLM_INPUT_LOG_DIR / now.strftime("%Y%m%d") / session_id
        log_dir.mkdir(parents=True, exist_ok=True)

        # 한 사용자 턴 안의 반복 LLM 호출을 파일명에서 바로 구분할 수 있게 합니다.
        file_path = _build_unique_file_path(log_dir, now, context)
        content = json.dumps(
            {
                "logged_at": now.isoformat(),
                "context": context,
                **payload,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        # LLM 호출 직후 프로세스가 종료되어도 어떤 입력이 전송됐는지 남기기 위해 동기화합니다.
        with file_path.open("w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        _fsync_directory(log_dir)
        return file_path
    except OSError:
        logger.exception("Failed to write LLM input debug file")
        return None


def _build_unique_file_path(
    log_dir: Path,
    logged_at: datetime,
    context: LlmInputDebugContext,
) -> Path:
    """동일 millisecond에 여러 파일이 생겨도 덮어쓰지 않는 경로를 만듭니다."""
    timestamp = logged_at.strftime("%H%M%S_%f")
    event = _safe_part(context.get("event"), fallback="input-items")
    user_message_id = _safe_part(context.get("user_message_id"), fallback="no-turn")
    agent_run_id = _safe_part(context.get("agent_run_id"), fallback="no-run")
    iteration = context.get("iteration")
    iteration_part = (
        f"iter-{int(iteration):02d}" if isinstance(iteration, int) else "iter-00"
    )
    stem = (
        f"{timestamp}__{event}__turn-{user_message_id}"
        f"__run-{agent_run_id}__{iteration_part}"
    )
    file_path = log_dir / f"{stem}.json"
    suffix = 1
    while file_path.exists():
        file_path = log_dir / f"{stem}__{suffix}.json"
        suffix += 1
    return file_path


def _safe_part(value: object, *, fallback: str) -> str:
    """외부 입력 ID를 경로 조각으로 안전하게 정규화합니다."""
    if not isinstance(value, str) or not value.strip():
        return fallback
    return _SAFE_PATH_CHARS.sub("-", value.strip())[:120] or fallback


def _fsync_directory(path: Path) -> None:
    """새 파일명이 crash 이후에도 보이도록 디렉터리 메타데이터를 동기화합니다."""
    directory_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
