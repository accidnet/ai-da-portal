import json
from typing import Literal, cast

from agents.prompt_loader import load_prompt
from agents.state import AgentState, AgentStateSnapshot, AgentRoute, PlanStep
from application.datasets.service import DatasetApplicationService
from domain.shared import AnalyticsPayload, WorkspacePayload
from infrastructure.ai.client import AiClient, AiClientError
from shared.integrations.ai.contracts import (
    Message,
    FunctionCall,
    FunctionCallOutput,
    InputItemList,
    ResponseInputText,
)
from tools import registry


class BaseAgent:
    """공통 LLM 호출과 tool 실행 상태 관리를 담당하는 agent 기반 클래스입니다."""

    def __init__(
        self,
        *,
        llm_client: AiClient,
        dataset_service: DatasetApplicationService,
    ) -> None:
        self._llm_client = llm_client
        self._dataset_service = dataset_service

    def snapshot_state(self, state: AgentState) -> AgentStateSnapshot:
        """agent 내부 상태를 API와 저장소에서 쓰는 스냅샷으로 정규화합니다."""
        route = cast(AgentRoute, state.get("route", "conversation"))
        assistant_message = self._read_string(state.get("assistant_message")) or ""
        analytics = state.get("analytics")
        workspace = state.get("workspace")
        plan = [
            cast(PlanStep, step)
            for step in state.get("plan", [])
            if isinstance(step, dict)
        ]
        status = cast(
            str,
            state.get("status", "completed" if assistant_message else "queued"),
        )
        if not assistant_message and (
            isinstance(analytics, AnalyticsPayload)
            or isinstance(workspace, WorkspacePayload)
        ):
            assistant_message = (
                "백엔드 분석은 완료됐어요. 요약과 시각화 결과를 확인해 주세요."
            )

        return {
            "route": route,
            "assistant_message": assistant_message,
            "used_tools": [
                tool for tool in state.get("used_tools", []) if isinstance(tool, str)
            ],
            "plan": plan,
            "plan_explanation": (
                state.get("plan_explanation")
                if isinstance(state.get("plan_explanation"), str)
                else None
            ),
            "analytics": (
                analytics if isinstance(analytics, AnalyticsPayload) else None
            ),
            "workspace": (
                workspace if isinstance(workspace, WorkspacePayload) else None
            ),
            "resolved_dataset_id": self._read_string(state.get("resolved_dataset_id")),
            "analysis_type": self._read_string(state.get("analysis_type")),
            "status": cast(
                Literal[
                    "queued",
                    "profiling",
                    "running_analysis",
                    "completed",
                    "failed",
                ],
                status,
            ),
        }

    def _build_developer_input(self, *, dataset_ids: list[str]) -> Message:
        """업로드 데이터셋 정보를 모델 입력용 개발자 메시지로 활용합니다."""
        payload = {"dataset_ids": dataset_ids}
        return Message(
            role="developer",
            content=(ResponseInputText(text=f"다음의 정보를 활용하세요.\n{payload}"),),
        )

    def _build_initial_inputs(
        self, *, message: str, dataset_ids: list[str]
    ) -> list[dict[str, object]]:
        """초기 LLM 요청 input 목록을 구성합니다."""
        inputs = []
        if dataset_ids:
            inputs.append(self._build_developer_input(dataset_ids=dataset_ids))

        inputs.append(Message(role="user", content=(ResponseInputText(text=message),)))

        return InputItemList(items=inputs).to_payload()

    def _execute_function_call_items(
        self, function_call_items: list[FunctionCall] | None
    ) -> dict[str, dict[str, object]]:
        """function_call 목록을 실행하고 다음 input용 output item을 이름별로 반환합니다."""
        if not function_call_items:
            return {}

        function_call_outputs: dict[str, dict[str, object]] = {}
        for function_call in function_call_items:
            tool_result = registry.execute_tool(
                function_call.name,
                function_call.arguments,
            )
            function_call_output_params = function_call.model_dump(
                mode="json",
                include={"call_id", "id", "status"},
                exclude_none=True,
            )
            function_call_outputs[function_call.name] = FunctionCallOutput(
                **function_call_output_params,
                output=json.dumps(tool_result, ensure_ascii=False),
            ).model_dump(mode="json", exclude_none=True)
        return function_call_outputs

    def _build_state_event(self, state: AgentState) -> dict[str, object]:
        """프론트로 전달할 agent.state 이벤트 payload를 구성합니다."""
        return {
            "type": "agent.state",
            "state": self._serialize_snapshot(self.snapshot_state(state)),
        }

    def _serialize_snapshot(self, snapshot: AgentStateSnapshot) -> dict[str, object]:
        return {
            "route": snapshot["route"],
            "assistant_message": snapshot["assistant_message"],
            "used_tools": snapshot["used_tools"],
            "plan": snapshot["plan"],
            "plan_explanation": snapshot["plan_explanation"],
            "analytics": (
                snapshot["analytics"].model_dump(mode="json")
                if snapshot["analytics"] is not None
                else None
            ),
            "workspace": (
                snapshot["workspace"].model_dump(mode="json")
                if snapshot["workspace"] is not None
                else None
            ),
            "resolved_dataset_id": snapshot["resolved_dataset_id"],
            "analysis_type": snapshot["analysis_type"],
            "status": snapshot["status"],
        }

    def _build_llm_request_kwargs(
        self, input_items: list[dict[str, object]]
    ) -> dict[str, object]:
        # 외부 LLM API 호출에 필요한 요청 파라미터를 구성합니다.
        return {
            "instructions": load_prompt("base.md"),
            "input": input_items,
            "tools": registry.get_tool_definitions(),
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "reasoning": {"effort": "medium"},
        }

    def _read_string(self, value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _require_string(self, state: AgentState, key: str) -> str:
        value = state.get(key)
        if isinstance(value, str) and value:
            return value
        raise AiClientError(f"Agent state is missing required field: {key}")
