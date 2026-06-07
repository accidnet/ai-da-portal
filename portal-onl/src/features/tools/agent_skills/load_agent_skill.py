from features.agents.skill_loader import load_agent_skill
from features.tools.dto import ToolExecutionResult
from shared.integrations.ai.contracts import Function


def tool_definition() -> dict[str, object]:
    """Agent skill Markdown 전문을 로드하는 tool 정의를 반환합니다."""
    definition = Function(
        name="load_agent_skill",
        description=(
            "base instructions의 프로젝트 skill catalog에 있는 skill Markdown 전문을 읽습니다. "
            "특정 skill의 세부 지침이 필요한 경우 호출합니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "읽을 skill 이름입니다. 예: data_analysis_cli",
                },
            },
            "required": ["skill_name"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 요청한 skill 문서를 반환합니다."""
    skill_name = arguments.get("skill_name")
    if not isinstance(skill_name, str):
        return ToolExecutionResult[object](
            ok=False,
            error="skill_name is required.",
        ).model_dump(mode="json", exclude_none=True)

    try:
        summary, content = load_agent_skill(skill_name)
    except ValueError as exc:
        return ToolExecutionResult[object](ok=False, error=str(exc)).model_dump(
            mode="json",
            exclude_none=True,
        )

    return ToolExecutionResult[dict[str, object]](
        ok=True,
        data={
            "skill_name": summary.name,
            "title": summary.title,
            "description": summary.description,
            "content": content,
        },
    ).model_dump(mode="json", exclude_none=True)
