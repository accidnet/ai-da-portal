import os

from core.utils import read_string
from features.tools.dto import ToolExecutionResult
from features.tools.workspace_files.context import resolve_workspace_path
from shared.integrations.ai.contracts import Function

MAX_WRITE_BYTES = 1_000_000


def tool_definition() -> dict[str, object]:
    """워크스페이스 로컬 파일 쓰기 tool 정의를 반환합니다."""
    definition = Function(
        name="write_workspace_file",
        description=(
            "현재 워크스페이스 로컬 저장소에 UTF-8 텍스트 파일을 생성하거나 갱신합니다. "
            "path는 워크스페이스 루트 기준 상대 경로만 허용되며 필요한 상위 폴더는 자동 생성됩니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "쓸 파일의 워크스페이스 상대 경로입니다.",
                },
                "content": {
                    "type": "string",
                    "description": "파일에 저장할 UTF-8 텍스트 내용입니다.",
                },
                "overwrite": {
                    "type": ["boolean", "null"],
                    "description": "기존 파일을 덮어쓸지 여부입니다. 기본값을 쓰려면 null입니다.",
                },
            },
            "required": ["path", "content", "overwrite"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """워크스페이스 로컬 저장소에 텍스트 파일을 저장합니다."""
    try:
        path = _read_path(arguments.get("path"))
        content = _read_content(arguments.get("content"))
        overwrite = arguments.get("overwrite") is not False
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > MAX_WRITE_BYTES:
            raise ValueError("content is too large.")

        target_path = resolve_workspace_path(path)
        if target_path.exists() and not overwrite:
            raise ValueError("File already exists.")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content_bytes)
        os.utime(target_path.parent, None)
    except ValueError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )

    return ToolExecutionResult[dict[str, object]](
        ok=True,
        data={
            "path": path,
            "size_bytes": len(content_bytes),
        },
    ).model_dump(mode="json", exclude_none=True)


def _read_path(value: object) -> str:
    """tool 입력에서 저장 경로를 읽습니다."""
    path = read_string(value)
    if path is None:
        raise ValueError("path is required.")
    if path.endswith("/"):
        raise ValueError("path must be a file path.")
    return path


def _read_content(value: object) -> str:
    """tool 입력에서 저장할 텍스트 내용을 읽습니다."""
    if not isinstance(value, str):
        raise ValueError("content is required.")
    return value
