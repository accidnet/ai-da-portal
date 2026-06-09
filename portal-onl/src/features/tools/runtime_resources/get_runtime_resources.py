from features.agents.runtime_resources import collect_runtime_resource_payload
from features.tools.dto import ToolExecutionResult


def tool_definition() -> dict[str, object]:
    """현재 백엔드 런타임 자원 상태를 조회하는 agent tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "get_runtime_resources",
        "description": (
            "현재 백엔드의 가용 메모리, 프로세스 메모리, 루트 디스크 여유 공간, CPU 수, "
            "1분 load average를 조회합니다. 큰 데이터 처리나 임시 파일 생성 전에 자원 상태가 필요할 때 사용합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 현재 런타임 자원 상태를 반환합니다."""
    # 자원 상태는 호출 시점마다 달라지므로 developer message 대신 tool 실행 시점에 수집합니다.
    return ToolExecutionResult[dict[str, object]](
        ok=True,
        data=collect_runtime_resource_payload(),
    ).model_dump(mode="json", exclude_none=True)

