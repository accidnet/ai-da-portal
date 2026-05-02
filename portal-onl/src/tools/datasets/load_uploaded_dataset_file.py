from collections.abc import Callable


type StringReader = Callable[[object], str | None]


def tool_definition() -> dict[str, object]:
    """업로드 파일 재조회용 에이전트 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "load_uploaded_dataset_file",
        "description": (
            "사용자가 업로드한 파일명을 기준으로 백엔드의 고정 업로드 경로에서 파일을 다시 불러옵니다. pandas로 로드한 뒤 행/열 수, 컬럼, 타입, 결측치, 미리보기를 반환합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "로드할 업로드 파일명입니다. 에이전트에 전달된 available_uploaded_filenames 중 하나를 사용합니다.",
                }
            },
            "required": ["filename"],
            "additionalProperties": False,
        },
    }


def execute(
    arguments: dict[str, object],
    *,
    dataset_service,
    read_string: StringReader,
) -> dict[str, object]:
    """파일명으로 업로드 데이터셋을 찾아 요약 정보를 반환합니다."""
    filename = read_string(arguments.get("filename"))
    if filename is None:
        return {"ok": False, "error": "filename is required."}

    try:
        payload = dataset_service.load_uploaded_file_by_filename(filename)
    except FileNotFoundError:
        return {
            "ok": False,
            "error": f"Uploaded file not found: {filename}",
        }
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    return {"ok": True, **payload}
