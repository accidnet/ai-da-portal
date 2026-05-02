import json
import logging
from typing import Literal, cast

from agents.prompt_loader import load_prompt
from agents.state import AgentState, AgentStateSnapshot, AgentRoute, PlanStep
from domain.analyses.service import AnalysisService
from application.datasets.service import DatasetApplicationService
from domain.shared import AnalyticsPayload, WorkspacePayload
from infrastructure.ai.client import AiClient, AiClientError, coerce_optional_dict
from infrastructure.ai.input_models import (
    Message,
    EasyInputMessage,
    FunctionCall,
    FunctionCallOutput,
    InputItemList,
    ResponseInputText,
)
from tools import registry

logger = logging.getLogger(__name__)


class BaseAgent:
    def __init__(
        self,
        *,
        llm_client: AiClient,
        dataset_service: DatasetApplicationService,
        analysis_service: AnalysisService,
    ) -> None:
        self._llm_client = llm_client
        self._dataset_service = dataset_service
        self._analysis_service = analysis_service

    def snapshot_state(self, state: AgentState) -> AgentStateSnapshot:
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
        """업로드 데이터셋 정보를 모델 입력용 개발자 메시지로 변환합니다."""

        payload = {"dataset_ids": dataset_ids}
        return Message(
            role="developer",
            content=(ResponseInputText(text=f"다음의 정보를 활용하세요.\n{payload}"),),
        )

    def _build_inputs(
        self,
        *,
        message: str,
        dataset_ids: list[str],
        inputs: list | None = None
    ) -> list[dict[str, object]]:

        if not inputs:
            inputs = []
        if dataset_ids:
            inputs.append(self._build_developer_input(dataset_ids=dataset_ids))

        inputs.append(Message(role="user", content=(ResponseInputText(text=message),)))

        return InputItemList(items=inputs).to_payload()

    def _execute_function_call(
        self, state: AgentState, function_call: FunctionCall
    ) -> dict[str, object]:
        state["used_tools"] = [*state.get("used_tools", []), function_call.name]
        return registry.execute_tool(
            function_call.name,
            state,
            self._parse_function_call_arguments(function_call),
            registry.ToolRuntimeContext(
                dataset_service=self._dataset_service,
                analysis_service=self._analysis_service,
                resolve_dataset_id=lambda tool_state, preferred_dataset_id: self._resolve_dataset_id(
                    state=tool_state,
                    preferred_dataset_id=preferred_dataset_id,
                ),
                available_dataset_ids=self._available_dataset_ids_from_state,
                read_string=self._read_string,
                read_bool=lambda value, default: self._read_bool(
                    value, default=default
                ),
                require_string=self._require_string,
            ),
        )

    def _parse_function_call_arguments(
        self, function_call: FunctionCall
    ) -> dict[str, object]:
        # Responses function_call arguments는 JSON 문자열이므로 도구 호출 직전에 dict로 변환합니다.
        if not function_call.arguments.strip():
            return {}
        loaded = json.loads(function_call.arguments)
        return loaded if isinstance(loaded, dict) else {}

    def _build_function_call_output_item(
        self,
        function_call: FunctionCall,
        tool_result: dict[str, object],
    ) -> dict[str, object]:
        # 함수 호출 결과는 다음 Responses input에 그대로 이어붙일 수 있는 형식으로 맞춥니다.
        return FunctionCallOutput(
            call_id=function_call.call_id,
            output=json.dumps(tool_result, ensure_ascii=False),
        ).to_payload()

    def _execute_response_function_calls(
        self, state: AgentState, response: dict[str, object]
    ) -> list[dict[str, object]]:
        tool_outputs: list[dict[str, object]] = []
        for function_call in self._extract_function_calls(response):
            tool_result = self._execute_function_call(state, function_call)
            tool_outputs.append(
                self._build_function_call_output_item(function_call, tool_result)
            )
        return tool_outputs

    def _build_state_event(self, state: AgentState) -> dict[str, object]:
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

    def _available_dataset_ids(self, dataset_ids: list[str]) -> list[str]:
        combined = [*dataset_ids]
        latest_dataset_id = self._dataset_service.get_latest_dataset_id()
        if latest_dataset_id:
            combined.append(latest_dataset_id)
        unique_ids: list[str] = []
        for dataset_id in combined:
            if dataset_id not in unique_ids:
                unique_ids.append(dataset_id)
        return unique_ids

    def _available_dataset_ids_from_state(self, state: AgentState) -> list[str]:
        return self._available_dataset_ids(state.get("dataset_ids", []))

    def _available_uploaded_filenames(self, dataset_ids: list[str]) -> list[str]:
        get_uploaded_filenames = getattr(
            self._dataset_service, "get_uploaded_filenames", None
        )
        if not callable(get_uploaded_filenames):
            return []
        return cast(list[str], get_uploaded_filenames(dataset_ids))

    def _resolve_dataset_id(
        self, *, state: AgentState, preferred_dataset_id: str | None
    ) -> str | None:
        candidates = [
            preferred_dataset_id,
            state.get("resolved_dataset_id"),
            *(state.get("dataset_ids", [])),
            self._dataset_service.get_latest_dataset_id(),
        ]
        for candidate in candidates:
            if candidate:
                return candidate
        return None

    def _extract_function_calls(
        self, response: dict[str, object]
    ) -> list[FunctionCall]:
        output = response.get("output")
        if not isinstance(output, list):
            return []

        function_calls: list[FunctionCall] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            call_id = item.get("call_id")
            name = item.get("name")
            arguments = item.get("arguments")
            if not isinstance(call_id, str) or not isinstance(name, str):
                continue
            serialized_arguments = arguments if isinstance(arguments, str) else "{}"
            function_calls.append(
                FunctionCall(
                    call_id=call_id,
                    name=name,
                    arguments=serialized_arguments,
                )
            )
        return function_calls

    def _extract_assistant_text(self, response: dict[str, object]) -> str | None:
        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = response.get("output")
        if not isinstance(output, list):
            return None

        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for entry in content:
                if not isinstance(entry, dict):
                    continue
                text = entry.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return "\n\n".join(parts)
        return None

    def _response_output_to_input_items(
        self, response: dict[str, object]
    ) -> list[dict[str, object]]:
        output = response.get("output")
        if not isinstance(output, list):
            assistant_text = self._extract_assistant_text(response)
            if not assistant_text:
                return []
            return InputItemList(
                items=(
                    EasyInputMessage(
                        role="assistant",
                        content=(ResponseInputText(text=assistant_text),),
                    ),
                )
            ).to_payload()

        input_items: list[dict[str, object]] = []
        for item in output:
            if not isinstance(item, dict):
                continue

            item_type = item.get("type")
            if item_type == "function_call":
                call_id = self._read_string(item.get("call_id"))
                name = self._read_string(item.get("name"))
                if not call_id or not name:
                    continue

                arguments = item.get("arguments")
                serialized_arguments = (
                    arguments
                    if isinstance(arguments, str)
                    else json.dumps(arguments or {}, ensure_ascii=False)
                )
                input_items.append(
                    FunctionCall(
                        arguments=serialized_arguments,
                        call_id=call_id,
                        name=name,
                        id=self._read_string(item.get("id")),
                        namespace=self._read_string(item.get("namespace")),
                        status=cast(
                            Literal["in_progress", "completed", "incomplete"] | None,
                            item.get("status"),
                        ),
                    ).to_payload()
                )
                continue

            if item_type == "function_call_output":
                call_id = self._read_string(item.get("call_id"))
                if not call_id:
                    continue

                output_payload = item.get("output")
                if isinstance(output_payload, list):
                    typed_output = tuple(
                        ResponseInputText(text=text)
                        for entry in output_payload
                        if isinstance(entry, dict)
                        and isinstance((text := entry.get("text")), str)
                    )
                    if not typed_output:
                        continue
                    input_items.append(
                        FunctionCallOutput(
                            call_id=call_id,
                            output=typed_output,
                            id=self._read_string(item.get("id")),
                            status=cast(
                                Literal["in_progress", "completed", "incomplete"]
                                | None,
                                item.get("status"),
                            ),
                        ).to_payload()
                    )
                    continue

                if isinstance(output_payload, str):
                    input_items.append(
                        FunctionCallOutput(
                            call_id=call_id,
                            output=output_payload,
                            id=self._read_string(item.get("id")),
                            status=cast(
                                Literal["in_progress", "completed", "incomplete"]
                                | None,
                                item.get("status"),
                            ),
                        ).to_payload()
                    )
                continue

            if item_type != "message":
                continue

            role = item.get("role")
            if role not in ("developer", "user", "assistant", "system"):
                continue

            content = item.get("content")
            if not isinstance(content, list):
                continue

            typed_content = tuple(
                ResponseInputText(text=text)
                for entry in content
                if isinstance(entry, dict)
                and isinstance((text := entry.get("text")), str)
                and text.strip()
            )
            if not typed_content:
                continue

            input_items.append(
                EasyInputMessage(
                    role=cast(
                        Literal["developer", "user", "assistant", "system"], role
                    ),
                    content=typed_content,
                ).to_payload()
            )

        return input_items

    def _extend_input_with_response(
        self,
        current_input: list[dict[str, object]],
        response: dict[str, object],
        *,
        tool_outputs: list[dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        # 다음 호출에는 기존 대화와 이번 응답 결과를 모두 누적합니다.
        return [
            *current_input,
            *self._response_output_to_input_items(response),
            *(tool_outputs or []),
        ]

    def _normalize_response_payload(
        self, response: dict[str, object]
    ) -> dict[str, object]:
        nested_response = coerce_optional_dict(response.get("response"))
        normalized = nested_response if nested_response is not None else dict(response)

        output_text = normalized.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            normalized["output_text"] = output_text.strip()
            return normalized

        extracted = self._extract_assistant_text(normalized)
        if extracted:
            normalized["output_text"] = extracted

        return normalized

    def _build_llm_request_kwargs(
        self, inputs: list[dict[str, object]]
    ) -> dict[str, object]:
        # 외부 LLM API 호출에 필요한 요청 파라미터를 구성합니다.
        return {
            "instructions": load_prompt("base.md"),
            "input": inputs,
            "tools": registry.get_tool_definitions(),
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "reasoning": {"effort": "medium"},
        }

    def _read_bool(self, value: object, *, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        return default

    def _read_string(self, value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _require_string(self, state: AgentState, key: str) -> str:
        value = state.get(key)
        if isinstance(value, str) and value:
            return value
        raise AiClientError(f"Agent state is missing required field: {key}")
