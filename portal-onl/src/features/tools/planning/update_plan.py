from typing import Literal, TypedDict, cast

from core.utils import read_string
from features.tools.dto import ToolExecutionResult


_PLAN_STATUSES = ("pending", "in_progress", "completed")


class PlanStep(TypedDict):
    """tool 응답에서 사용하는 계획 단계 payload입니다."""

    step: str
    status: Literal["pending", "in_progress", "completed"]


def tool_definition() -> dict[str, object]:
    """작업 계획 갱신용 에이전트 tool 정의를 반환합니다."""
    return {
        "type": "function",
        "name": "update_plan",
        "description": (
            "복잡한 작업을 위한 진행 계획을 갱신합니다. 선택적으로 explanation을 포함할 수 있고, "
            "plan에는 step과 status를 가진 단계 목록을 전달해야 합니다. 동시에 in_progress는 최대 하나만 허용됩니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "explanation": {
                    "type": ["string", "null"],
                    "description": "계획을 새로 만들거나 수정한 이유를 짧게 설명합니다.",
                },
                "plan": {
                    "type": "array",
                    "description": "현재 작업 계획 단계 목록입니다.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step": {
                                "type": "string",
                                "description": "짧고 검증 가능한 작업 단계입니다.",
                            },
                            "status": {
                                "type": "string",
                                "enum": list(_PLAN_STATUSES),
                                "description": (
                                    f"{', '.join(_PLAN_STATUSES)} 중 하나입니다."
                                ),
                            },
                        },
                        "required": ["step", "status"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["explanation", "plan"],
            "additionalProperties": False,
        },
    }


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments를 검증해 정규화된 계획 정보를 반환합니다."""
    explanation = _read_explanation(arguments.get("explanation"))
    if explanation is _INVALID_EXPLANATION:
        return _error_result("explanation must be a string.")

    plan_result = _read_plan_steps(arguments.get("plan"))
    if isinstance(plan_result, str):
        return _error_result(plan_result)

    return _success_result(
        explanation=cast(str | None, explanation),
        plan=plan_result,
    )


_INVALID_EXPLANATION = object()


def _read_explanation(value: object) -> str | object | None:
    """선택 입력인 explanation을 공백 제거된 문자열로 정규화합니다."""
    if value is None:
        return None
    if not isinstance(value, str):
        return _INVALID_EXPLANATION
    return read_string(value)


def _read_plan_steps(value: object) -> list[PlanStep] | str:
    """plan argument를 검증하고 AgentState에 저장 가능한 단계 목록으로 변환합니다."""
    if not isinstance(value, list):
        return "plan must be an array."

    plan: list[PlanStep] = []
    for raw_step in value:
        step_result = _read_plan_step(raw_step)
        if isinstance(step_result, str):
            return step_result
        plan.append(step_result)

    in_progress_count = sum(1 for item in plan if item["status"] == "in_progress")
    if in_progress_count > 1:
        return "at most one plan item can be in_progress."

    return plan


def _read_plan_step(value: object) -> PlanStep | str:
    """단일 plan item을 검증하고 공백이 제거된 PlanStep으로 변환합니다."""
    if not isinstance(value, dict):
        return "each plan item must be an object."

    step = read_string(value.get("step"))
    if step is None:
        return "each plan item needs a non-empty step."

    status = value.get("status")
    if status not in _PLAN_STATUSES:
        return "status must be one of pending, in_progress, completed."

    # status는 enum 검증을 통과한 문자열 literal로만 state에 저장합니다.
    normalized_status = cast(PlanStep, {"step": step, "status": status})
    return normalized_status


def _success_result(
    *,
    explanation: str | None,
    plan: list[PlanStep],
) -> dict[str, object]:
    """계획 갱신 성공 결과를 공통 DTO 형식으로 반환합니다."""
    data = {
        "message": "Plan updated",
        "explanation": explanation,
        "plan": plan,
    }
    return ToolExecutionResult[dict[str, object]](ok=True, data=data).model_dump(
        mode="json",
        exclude_none=True,
    )


def _error_result(message: str) -> dict[str, object]:
    """계획 갱신 실패 결과를 공통 DTO 형식으로 반환합니다."""
    return ToolExecutionResult[object](ok=False, error=message).model_dump(
        mode="json",
        exclude_none=True,
    )
