import shutil

from core.utils import read_string
from features.tools.dto import ToolExecutionResult
from features.tools.workspace_files.context import resolve_workspace_path
from shared.integrations.ai.contracts import Function


def tool_definition() -> dict[str, object]:
    """워크스페이스 로컬 경로 삭제 tool 정의를 반환합니다."""
    definition = Function(
        name="delete_workspace_path",
        description=(
            "현재 워크스페이스 로컬 저장소의 파일 또는 빈 폴더를 삭제합니다. "
            "폴더와 하위 항목을 함께 지울 때는 recursive를 true로 지정합니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "삭제할 워크스페이스 상대 경로입니다.",
                },
                "recursive": {
                    "type": ["boolean", "null"],
                    "description": "폴더 하위 항목까지 삭제할지 여부입니다.",
                },
            },
            "required": ["path", "recursive"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """워크스페이스 로컬 저장소의 파일 또는 폴더를 삭제합니다."""
    try:
        path = _read_path(arguments.get("path"))
        recursive = arguments.get("recursive") is True
        target_path = resolve_workspace_path(path)
        if not target_path.exists():
            raise ValueError("Path does not exist.")
        if target_path.is_dir():
            if recursive:
                shutil.rmtree(target_path)
            else:
                target_path.rmdir()
        else:
            target_path.unlink()
    except OSError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )
    except ValueError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )

    return ToolExecutionResult[dict[str, object]](
        ok=True,
        data={"path": path, "deleted": True},
    ).model_dump(mode="json", exclude_none=True)


def _read_path(value: object) -> str:
    """tool 입력에서 삭제 경로를 읽습니다."""
    path = read_string(value)
    if path is None:
        raise ValueError("path is required.")
    if path in {".", "/"}:
        raise ValueError("workspace root cannot be deleted by this tool.")
    return path
