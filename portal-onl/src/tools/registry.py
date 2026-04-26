from tools import update_plan


def get_tool_definitions() -> list[dict[str, object]]:
    """에이전트에서 사용하는 툴 정의 목록을 중앙 관리합니다."""

    return [
        update_plan.tool_definition(),
        update_plan.inspect_dataset_context_tool_definition(),
        update_plan.run_portal_analysis_tool_definition(),
        update_plan.load_uploaded_dataset_file_tool_definition(),
    ]
