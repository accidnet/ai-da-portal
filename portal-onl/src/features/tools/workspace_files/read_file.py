from core.utils import read_string
from features.tools.dto import ToolExecutionResult
from features.tools.workspace_files.context import resolve_workspace_path
from shared.integrations.ai.contracts import Function

DEFAULT_MAX_BYTES = 200_000
MAX_READ_BYTES = 1_000_000


def tool_definition() -> dict[str, object]:
    """워크스페이스 로컬 파일 읽기 tool 정의를 반환합니다."""
    definition = Function(
        name="read_workspace_file",
        description=(
            "현재 워크스페이스 로컬 저장소의 텍스트 파일 내용을 읽습니다. "
            "path는 워크스페이스 루트 기준 상대 경로만 허용됩니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "읽을 파일의 워크스페이스 상대 경로입니다.",
                },
                "max_bytes": {
                    "type": ["integer", "null"],
                    "description": "읽을 최대 바이트 수입니다.",
                    "minimum": 1,
                    "maximum": MAX_READ_BYTES,
                },
            },
            "required": ["path", "max_bytes"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """워크스페이스 로컬 텍스트 파일 내용을 반환합니다."""
    try:
        path = _read_path(arguments.get("path"))
        max_bytes = _read_max_bytes(arguments.get("max_bytes"))
        target_path = resolve_workspace_path(path)
        if not target_path.is_file():
            raise ValueError("Path must be an existing file.")
        content_bytes = target_path.read_bytes()[:max_bytes]
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return ToolExecutionResult[object](
            ok=False,
            error="File is not valid UTF-8 text.",
        ).model_dump(mode="json", exclude_none=True)
    except ValueError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )

    return ToolExecutionResult[dict[str, object]](
        ok=True,
        data={
            "path": path,
            "content": content,
            "truncated": target_path.stat().st_size > max_bytes,
        },
    ).model_dump(mode="json", exclude_none=True)


def _read_path(value: object) -> str:
    """tool 입력에서 파일 경로를 읽습니다."""
    path = read_string(value)
    if path is None:
        raise ValueError("path is required.")
    return path


def _read_max_bytes(value: object) -> int:
    """tool 입력의 읽기 크기 제한을 정규화합니다."""
    if isinstance(value, int):
        return min(max(value, 1), MAX_READ_BYTES)
    return DEFAULT_MAX_BYTES
