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


def inspect_dataset_context_tool_definition() -> dict[str, object]:
    return {
        "type": "function",
        "name": "inspect_dataset_context",
        "description": (
            "업로드된 데이터의 구조, 컬럼, 품질, 범위, 사용 가능한 행에 대한 질문에 답하기 전에 데이터셋 프로필과 미리보기를 확인합니다. 상관관계나 추세 분석 같은 실제 분석 결론에는 이 함수를 사용하지 마세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": ["string", "null"],
                    "description": "확인할 특정 데이터셋 ID입니다. null이면 현재 사용할 수 있는 가장 적절한 데이터셋을 확인합니다.",
                },
                "include_preview": {
                    "type": "boolean",
                    "description": "표 형태의 미리보기 행을 포함할지 여부입니다.",
                    "default": True,
                },
                "include_profile": {
                    "type": "boolean",
                    "description": "데이터셋 프로파일 통계를 포함할지 여부입니다.",
                    "default": True,
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    }


def run_portal_analysis_tool_definition() -> dict[str, object]:
    return {
        "type": "function",
        "name": "run_portal_analysis",
        "description": (
            "백엔드 데이터셋 프로파일링 또는 분석을 실행하고 최종 답변에 사용할 구조화된 결과를 반환합니다. 업로드된 데이터의 계산 결과나 시각 요약에 근거해야 하는 답변에는 이 함수를 사용하세요."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "route": {
                    "type": "string",
                    "enum": ["dataset_analysis", "analysis_request"],
                    "description": "데이터셋 개요나 프로파일 작업에는 dataset_analysis를, 구체적인 분석 질문에는 analysis_request를 사용합니다.",
                },
                "analysis_type": {
                    "type": "string",
                    "enum": [
                        "dataset_profile",
                        "descriptive_summary",
                        "correlation",
                        "trend",
                        "grouped_aggregation",
                        "anomaly_detection",
                    ],
                    "description": "실행할 백엔드 분석 유형입니다.",
                },
                "dataset_id": {
                    "type": ["string", "null"],
                    "description": "분석할 특정 데이터셋 ID입니다. null이면 자동으로 결정합니다.",
                },
                "prompt": {
                    "type": ["string", "null"],
                    "description": "분석 요청을 위한 선택적 추가 지시문입니다.",
                },
            },
            "required": ["route", "analysis_type"],
            "additionalProperties": False,
        },
    }


def load_uploaded_dataset_file_tool_definition() -> dict[str, object]:
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
