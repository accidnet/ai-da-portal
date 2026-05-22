import subprocess
from pathlib import Path

from core.utils import read_string
from features.tools.dto import ToolExecutionResult
from features.tools.workspace_files.context import (
    WorkspaceFileContext,
    require_workspace_file_context,
)
from shared.integrations.ai.contracts import Function

DEFAULT_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 120
DEFAULT_MAX_OUTPUT_BYTES = 200_000
MAX_OUTPUT_BYTES = 1_000_000


def tool_definition() -> dict[str, object]:
    """워크스페이스 로컬 CLI command 실행 tool 정의를 반환합니다."""
    definition = Function(
        name="run_workspace_cli_command",
        description=(
            "현재 워크스페이스 로컬 저장소를 작업 디렉터리로 사용해 CLI command를 실행합니다. "
            "셸 문법이 아닌 argv 배열로 실행되며, 임시 파일 처리나 경량 분석 명령에 사용합니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "array",
                    "description": (
                        "실행할 명령과 인자 목록입니다. 예: [\"python\", \"script.py\"]"
                    ),
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 64,
                },
                "workspace_id": {
                    "type": "string",
                    "description": "명령을 실행할 현재 워크스페이스 ID입니다.",
                },
                "cwd": {
                    "type": ["string", "null"],
                    "description": (
                        "명령을 실행할 워크스페이스 폴더 기준 상대 경로입니다. null이면 워크스페이스 폴더 루트입니다."
                    ),
                },
                "timeout_seconds": {
                    "type": ["integer", "null"],
                    "description": "명령 실행 제한 시간입니다.",
                    "minimum": 1,
                    "maximum": MAX_TIMEOUT_SECONDS,
                },
                "max_output_bytes": {
                    "type": ["integer", "null"],
                    "description": "stdout/stderr 각각 반환할 최대 바이트 수입니다.",
                    "minimum": 1,
                    "maximum": MAX_OUTPUT_BYTES,
                },
            },
            "required": [
                "command",
                "workspace_id",
                "cwd",
                "timeout_seconds",
                "max_output_bytes",
            ],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """워크스페이스 로컬 저장소 안에서 CLI command를 실행합니다."""
    try:
        workspace_id = _read_workspace_id(arguments.get("workspace_id"))
        context = _require_matching_workspace_context(workspace_id)
        command = _read_command(arguments.get("command"))
        cwd = read_string(arguments.get("cwd")) or ""
        timeout_seconds = _read_timeout_seconds(arguments.get("timeout_seconds"))
        max_output_bytes = _read_max_output_bytes(arguments.get("max_output_bytes"))
        working_dir = _resolve_cli_working_dir(context, cwd)
        if not working_dir.exists():
            raise ValueError("cwd does not exist.")
        if not working_dir.is_dir():
            raise ValueError("cwd must be a directory.")

        # 셸을 거치지 않아 명령 문자열 해석과 의도치 않은 redirection을 피합니다.
        completed = subprocess.run(
            command,
            cwd=working_dir,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stdout_truncated = _decode_output(exc.stdout, max_output_bytes)
        stderr, stderr_truncated = _decode_output(exc.stderr, max_output_bytes)
        return ToolExecutionResult[dict[str, object]](
            ok=False,
            data={
                "command": command if "command" in locals() else [],
                "workspace_id": workspace_id if "workspace_id" in locals() else None,
                "cwd": cwd if "cwd" in locals() else "",
                "timed_out": True,
                "timeout_seconds": timeout_seconds
                if "timeout_seconds" in locals()
                else DEFAULT_TIMEOUT_SECONDS,
                "stdout": stdout,
                "stderr": stderr,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            },
            error="Command timed out.",
        ).model_dump(mode="json", exclude_none=True)
    except OSError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )
    except ValueError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )

    stdout, stdout_truncated = _decode_output(completed.stdout, max_output_bytes)
    stderr, stderr_truncated = _decode_output(completed.stderr, max_output_bytes)
    return ToolExecutionResult[dict[str, object]](
        ok=completed.returncode == 0,
        data={
            "command": command,
            "workspace_id": workspace_id,
            "cwd": cwd,
            "exit_code": completed.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        },
        error=None if completed.returncode == 0 else "Command failed.",
    ).model_dump(mode="json", exclude_none=True)


def _read_command(value: object) -> list[str]:
    """tool 입력에서 subprocess argv 목록을 읽습니다."""
    if not isinstance(value, list) or not value:
        raise ValueError("command is required.")
    if len(value) > 64:
        raise ValueError("command is too long.")

    command: list[str] = []
    for part in value:
        text = read_string(part)
        if text is None:
            raise ValueError("command must contain non-empty strings only.")
        command.append(text)
    return command


def _read_workspace_id(value: object) -> str:
    """tool 입력에서 대상 워크스페이스 ID를 읽습니다."""
    workspace_id = read_string(value)
    if workspace_id is None:
        raise ValueError("workspace_id is required.")
    return workspace_id


def _require_matching_workspace_context(workspace_id: str) -> WorkspaceFileContext:
    """현재 agent context와 다른 워크스페이스 명령 실행을 차단합니다."""
    context = require_workspace_file_context()
    if context.workspace_id != workspace_id:
        raise ValueError("workspace_id does not match the current workspace context.")
    if not context.local_path.exists() or not context.local_path.is_dir():
        raise ValueError("Workspace local storage does not exist.")
    return context


def _resolve_cli_working_dir(
    context: WorkspaceFileContext,
    relative_path: str,
) -> Path:
    """CLI 실행 경로를 기존 워크스페이스 폴더 내부로 제한합니다."""
    workspace_root = context.local_path.resolve()
    requested_path = (workspace_root / relative_path).resolve()
    if requested_path != workspace_root and workspace_root not in requested_path.parents:
        raise ValueError("cwd must stay inside the workspace local storage.")
    return requested_path


def _read_timeout_seconds(value: object) -> int:
    """tool 입력의 timeout 값을 정규화합니다."""
    if isinstance(value, int):
        return min(max(value, 1), MAX_TIMEOUT_SECONDS)
    return DEFAULT_TIMEOUT_SECONDS


def _read_max_output_bytes(value: object) -> int:
    """tool 입력의 출력 크기 제한 값을 정규화합니다."""
    if isinstance(value, int):
        return min(max(value, 1), MAX_OUTPUT_BYTES)
    return DEFAULT_MAX_OUTPUT_BYTES


def _decode_output(value: bytes | str | None, max_bytes: int) -> tuple[str, bool]:
    """subprocess 출력을 UTF-8 문자열과 잘림 여부로 변환합니다."""
    if value is None:
        return "", False

    raw = value.encode("utf-8", errors="replace") if isinstance(value, str) else value
    truncated = len(raw) > max_bytes
    content = raw[:max_bytes].decode("utf-8", errors="replace")
    return content, truncated
