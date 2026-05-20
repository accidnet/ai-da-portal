from pathlib import Path

from core.utils import read_string
from features.tools.dto import ToolExecutionResult
from features.tools.workspace_files.context import resolve_workspace_path
from shared.integrations.ai.contracts import Function


def tool_definition() -> dict[str, object]:
    """워크스페이스 로컬 파일 목록 조회 tool 정의를 반환합니다."""
    definition = Function(
        name="list_workspace_files",
        description=(
            "현재 워크스페이스 로컬 저장소 안의 파일과 폴더 목록을 조회합니다. "
            "path는 워크스페이스 루트 기준 상대 경로만 허용됩니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": ["string", "null"],
                    "description": "목록을 조회할 워크스페이스 상대 경로입니다. 생략하면 루트입니다.",
                },
                "recursive": {
                    "type": ["boolean", "null"],
                    "description": "하위 경로를 재귀적으로 조회할지 여부입니다.",
                },
                "max_entries": {
                    "type": ["integer", "null"],
                    "description": "반환할 최대 항목 수입니다.",
                    "minimum": 1,
                    "maximum": 500,
                },
            },
            "required": ["path", "recursive", "max_entries"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """워크스페이스 로컬 저장소의 파일 목록을 반환합니다."""
    try:
        path = read_string(arguments.get("path")) or ""
        recursive = arguments.get("recursive") is True
        max_entries = _read_max_entries(arguments.get("max_entries"))
        target_path = resolve_workspace_path(path)
        if not target_path.exists():
            raise ValueError("Path does not exist.")
        if not target_path.is_dir():
            raise ValueError("Path must be a directory.")
        entries = _list_entries(target_path, recursive=recursive, max_entries=max_entries)
    except ValueError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json", exclude_none=True
        )

    return ToolExecutionResult[dict[str, object]](
        ok=True,
        data={"path": path, "entries": entries},
    ).model_dump(mode="json", exclude_none=True)


def _read_max_entries(value: object) -> int:
    """tool 입력의 목록 제한 값을 정규화합니다."""
    if isinstance(value, int):
        return min(max(value, 1), 500)
    return 100


def _list_entries(
    root_path: Path,
    *,
    recursive: bool,
    max_entries: int,
) -> list[dict[str, object]]:
    """Path 항목을 JSON 응답용 목록으로 변환합니다."""
    workspace_root = resolve_workspace_path("").resolve()
    iterator = root_path.rglob("*") if recursive else root_path.iterdir()
    entries: list[dict[str, object]] = []
    for child in sorted(iterator, key=lambda item: item.as_posix()):
        if len(entries) >= max_entries:
            break
        stat = child.stat()
        entries.append(
            {
                "path": child.resolve().relative_to(workspace_root).as_posix(),
                "kind": "directory" if child.is_dir() else "file",
                "size_bytes": stat.st_size if child.is_file() else None,
                "updated_at": stat.st_mtime,
            }
        )
    return entries
