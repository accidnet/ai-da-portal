from typing import cast

from agents.state import AgentState, PlanStep


PLAN_STATUSES = ("pending", "in_progress", "completed")


def tool_definition() -> dict[str, object]:
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
                    "type": "string",
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
                                "enum": list(PLAN_STATUSES),
                                "description": "pending, in_progress, completed 중 하나입니다.",
                            },
                        },
                        "required": ["step", "status"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["plan"],
            "additionalProperties": False,
        },
    }


def execute(state: AgentState, arguments: dict[str, object]) -> dict[str, object]:
    raw_plan = arguments.get("plan")
    if not isinstance(raw_plan, list):
        return {"ok": False, "error": "plan must be an array."}

    explanation = arguments.get("explanation")
    if explanation is not None and not isinstance(explanation, str):
        return {"ok": False, "error": "explanation must be a string."}

    plan: list[PlanStep] = []
    in_progress_count = 0
    for raw_step in raw_plan:
        if not isinstance(raw_step, dict):
            return {"ok": False, "error": "each plan item must be an object."}

        step = raw_step.get("step")
        status = raw_step.get("status")
        if not isinstance(step, str) or not step.strip():
            return {"ok": False, "error": "each plan item needs a non-empty step."}
        if status not in PLAN_STATUSES:
            return {
                "ok": False,
                "error": "status must be one of pending, in_progress, completed.",
            }

        normalized_status = cast(str, status)
        if normalized_status == "in_progress":
            in_progress_count += 1

        plan.append({"step": step.strip(), "status": normalized_status})

    if in_progress_count > 1:
        return {
            "ok": False,
            "error": "at most one plan item can be in_progress.",
        }

    state["plan"] = plan
    state["plan_explanation"] = (
        explanation.strip() if isinstance(explanation, str) else None
    )
    return {
        "ok": True,
        "message": "Plan updated",
        "explanation": state["plan_explanation"],
        "plan": plan,
    }
