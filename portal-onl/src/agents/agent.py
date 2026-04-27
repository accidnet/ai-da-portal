import logging
import json
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from typing import Literal, cast

from agents.prompt_loader import load_prompt
from agents.stream_event_handlers import handle_stream_event
from agents.state import AgentState, AgentStateSnapshot, AgentRoute, PlanStep
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from domain.shared import AnalyticsPayload, WorkspacePayload
from infrastructure.llm.client import LlmClient, LlmClientError
from infrastructure.llm.input_models import (
    EasyInputMessage,
    FunctionCallOutput,
    InputItemList,
)
from tools import registry
from tools.function_call_runtime import resolve_output_item_function_call


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _FunctionCall:
    call_id: str
    name: str
    arguments: dict[str, object]


class Agent:
    def __init__(
        self,
        *,
        llm_client: LlmClient,
        dataset_service: DatasetService,
        analysis_service: AnalysisService,
    ) -> None:
        self._llm_client = llm_client
        self._dataset_service = dataset_service
        self._analysis_service = analysis_service

    def invoke(self, state: AgentState) -> AgentState:
        working_state = cast(AgentState, dict(state))
        working_state.setdefault("used_tools", [])
        working_state.setdefault("status", "queued")

        max_iterations = 6
        iteration_count = 0
        next_input: list[dict[str, object]] = self._build_initial_input(working_state)

        while True:
            if iteration_count >= max_iterations:
                break
            iteration_count += 1

            response = self._read_response_payload(
                self._llm_client.create_response(
                    instructions=load_prompt("base.md"),
                    input=next_input,
                    tools=registry.get_tool_definitions(),
                    tool_choice="auto",
                    parallel_tool_calls=False,
                    reasoning={"effort": "medium"},
                    max_output_tokens=900,
                )
            )

            response_id = response.get("id")
            if isinstance(response_id, str) and response_id:
                working_state["response_id"] = response_id

            function_calls = self._extract_function_calls(response)
            if function_calls:
                next_input = [
                    FunctionCallOutput(
                        call_id=function_call.call_id,
                        output=json.dumps(
                            self._execute_function_call(working_state, function_call),
                            ensure_ascii=False,
                        ),
                    ).to_payload()
                    for function_call in function_calls
                ]
                continue

            assistant_message = self._extract_assistant_text(response)
            if assistant_message:
                working_state["assistant_message"] = assistant_message
                working_state["status"] = "completed"
                working_state.setdefault("route", "conversation")
                break

            break

        working_state.setdefault("route", "conversation")
        return working_state

    def stream_invoke(
        self, state: AgentState
    ) -> Generator[dict[str, object], None, AgentState]:
        working_state = cast(AgentState, dict(state))
        working_state.setdefault("used_tools", [])
        working_state.setdefault("status", "queued")
        last_state_fingerprint: str | None = None
        next_input = self._build_initial_input(working_state)
        logger.debug("Agent stream input prepared next_input=%s", next_input)

        # TODO: 개발중에만 일시적으로 정해두고, 이후에는 사용자 설정에서 가능하도록 할 예정.
        max_iterations = 3
        iteration_count = 0

        while True:
            if iteration_count >= max_iterations:
                break
            iteration_count += 1

            stream_tool_outputs: list[dict[str, object]] = []

            def on_output_item_function_call(
                item: dict[str, object],
            ) -> dict[str, object] | None:
                nonlocal last_state_fingerprint

                function_call_output, stream_event, next_fingerprint = (
                    resolve_output_item_function_call(
                        item=item,
                        working_state=working_state,
                        extract_function_calls=self._extract_function_calls,
                        execute_function_call=self._execute_function_call,
                        build_state_event=self._build_state_event,
                        last_state_fingerprint=last_state_fingerprint,
                    )
                )
                last_state_fingerprint = next_fingerprint
                if function_call_output is not None:
                    stream_tool_outputs.append(function_call_output)
                return stream_event

            response_kwargs: dict[str, object] = {
                "instructions": load_prompt("base.md"),
                "input": next_input,
                "tools": registry.get_tool_definitions(),
                "tool_choice": "auto",
                "parallel_tool_calls": False,
                "reasoning": {"effort": "medium"},
                "max_output_tokens": 900,
            }
            logger.debug("Agent streaming response kwargs=%s", response_kwargs)

            response = yield from self._stream_response_payload(
                self._llm_client.create_response(**response_kwargs),
                handle_output_item_function_call=on_output_item_function_call,
            )

            response_id = response.get("id")
            if isinstance(response_id, str) and response_id:
                working_state["response_id"] = response_id

            if stream_tool_outputs:
                next_input = stream_tool_outputs
                continue

            function_calls = self._extract_function_calls(response)
            if function_calls:
                tool_outputs: list[dict[str, object]] = []
                for function_call in function_calls:
                    tool_result = self._execute_function_call(
                        working_state, function_call
                    )
                    tool_outputs.append(
                        FunctionCallOutput(
                            call_id=function_call.call_id,
                            output=json.dumps(tool_result, ensure_ascii=False),
                        ).to_payload()
                    )
                    state_event = self._build_state_event(working_state)
                    fingerprint = json.dumps(
                        state_event["state"], ensure_ascii=False, sort_keys=True
                    )
                    if fingerprint != last_state_fingerprint:
                        last_state_fingerprint = fingerprint
                        yield state_event
                next_input = tool_outputs
                continue

            assistant_message = self._extract_assistant_text(response)
            if assistant_message:
                working_state["assistant_message"] = assistant_message
                working_state["status"] = "completed"
                working_state.setdefault("route", "conversation")
                return working_state

            break

        working_state.setdefault("route", "conversation")
        return working_state

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

    def _build_initial_input(self, state: AgentState) -> list[dict[str, object]]:
        available_dataset_ids = self._available_dataset_ids(state)
        available_uploaded_filenames = self._available_uploaded_filenames(
            available_dataset_ids
        )
        payload = {
            "session_id": self._require_string(state, "session_id"),
            "requested_dataset_ids": state.get("dataset_ids", []),
            "session_dataset_ids": state.get("session_dataset_ids", []),
            "latest_dataset_id": self._dataset_service.get_latest_dataset_id(),
            "available_uploaded_filenames": available_uploaded_filenames,
            "latest_uploaded_filename": (
                available_uploaded_filenames[0]
                if available_uploaded_filenames
                else None
            ),
        }
        return InputItemList(
            items=(
                EasyInputMessage.from_text(
                    role="developer",
                    text="다음의 정보를 활용하세요.\n"
                    + json.dumps(payload, ensure_ascii=False),
                ),
                EasyInputMessage.from_text(
                    role="user",
                    text=self._require_string(state, "message"),
                ),
            )
        ).to_payload()

    def _execute_function_call(
        self, state: AgentState, function_call: _FunctionCall
    ) -> dict[str, object]:
        state["used_tools"] = [*state.get("used_tools", []), function_call.name]
        return registry.execute_tool(
            function_call.name,
            state,
            function_call.arguments,
            registry.ToolRuntimeContext(
                dataset_service=self._dataset_service,
                analysis_service=self._analysis_service,
                resolve_dataset_id=lambda tool_state, preferred_dataset_id: self._resolve_dataset_id(
                    state=tool_state,
                    preferred_dataset_id=preferred_dataset_id,
                ),
                available_dataset_ids=self._available_dataset_ids,
                read_string=self._read_string,
                read_bool=lambda value, default: self._read_bool(
                    value, default=default
                ),
                require_string=self._require_string,
            ),
        )

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

    def _available_dataset_ids(self, state: AgentState) -> list[str]:
        combined = [
            *state.get("dataset_ids", []),
            *state.get("session_dataset_ids", []),
        ]
        latest_dataset_id = self._dataset_service.get_latest_dataset_id()
        if latest_dataset_id:
            combined.append(latest_dataset_id)
        unique_ids: list[str] = []
        for dataset_id in combined:
            if dataset_id not in unique_ids:
                unique_ids.append(dataset_id)
        return unique_ids

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
            *(state.get("session_dataset_ids", [])),
            self._dataset_service.get_latest_dataset_id(),
        ]
        for candidate in candidates:
            if candidate:
                return candidate
        return None

    def _extract_function_calls(
        self, response: dict[str, object]
    ) -> list[_FunctionCall]:
        output = response.get("output")
        if not isinstance(output, list):
            return []

        function_calls: list[_FunctionCall] = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            call_id = item.get("call_id")
            name = item.get("name")
            arguments = item.get("arguments")
            if not isinstance(call_id, str) or not isinstance(name, str):
                continue
            parsed_arguments: dict[str, object] = {}
            if isinstance(arguments, str) and arguments.strip():
                loaded = json.loads(arguments)
                if isinstance(loaded, dict):
                    parsed_arguments = loaded
            function_calls.append(
                _FunctionCall(
                    call_id=call_id,
                    name=name,
                    arguments=parsed_arguments,
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

    def _read_response_payload(self, response: object) -> dict[str, object]:
        payload = self._coerce_optional_dict(response)
        if payload is not None:
            return self._normalize_response_payload(payload)
        return self._parse_stream_response(response)

    def _stream_response_payload(
        self,
        response: object,
        handle_output_item_function_call=None,
    ) -> Generator[dict[str, object], None, dict[str, object]]:
        payload = self._coerce_optional_dict(response)
        if payload is not None:
            return self._normalize_response_payload(payload)
        return (
            yield from self._parse_stream_response_events(
                response,
                handle_output_item_function_call=handle_output_item_function_call,
            )
        )

    def _parse_stream_response(self, stream: object) -> dict[str, object]:
        parser = self._parse_stream_response_events(stream)
        try:
            while True:
                next(parser)
        except StopIteration as stop:
            return stop.value

    def _parse_stream_response_events(
        self, stream: object, handle_output_item_function_call=None
    ) -> Generator[dict[str, object], None, dict[str, object]]:
        response_id: str | None = None
        final_text: str | None = None
        text_deltas: list[str] = []
        function_calls: dict[str, dict[str, object]] = {}

        close = getattr(stream, "close", None)
        try:
            for event in cast(Iterable[object], stream):
                payload = self._event_to_dict(event)
                response_payload = self._coerce_optional_dict(payload.get("response"))

                if response_payload is not None and response_id is None:
                    response_id = self._read_string(response_payload.get("id"))

                result = handle_stream_event(
                    payload=payload,
                    response_id=response_id,
                    response_payload=response_payload,
                    function_calls=function_calls,
                    text_deltas=text_deltas,
                    final_text=final_text,
                    coerce_optional_dict=self._coerce_optional_dict,
                    normalize_response_payload=self._normalize_response_payload,
                    handle_output_item_function_call=handle_output_item_function_call,
                )
                final_text = result["final_text"]

                completed_response = result["completed_response"]
                if isinstance(completed_response, dict):
                    return completed_response

                yielded_event = result["yielded_event"]
                if isinstance(yielded_event, dict):
                    yield yielded_event

                if result["handled"]:
                    continue
        finally:
            if callable(close):
                close()

        normalized: dict[str, object] = {}
        if response_id:
            normalized["id"] = response_id

        output = self._build_stream_output(function_calls, final_text, text_deltas)
        if output:
            normalized["output"] = output

        output_text = final_text or "".join(text_deltas).strip()
        if output_text:
            normalized["output_text"] = output_text

        return self._normalize_response_payload(normalized)

    def _build_stream_output(
        self,
        function_calls: dict[str, dict[str, object]],
        final_text: str | None,
        text_deltas: list[str],
    ) -> list[dict[str, object]]:
        output: list[dict[str, object]] = []
        for function_call in function_calls.values():
            output.append(function_call)

        message_text = final_text or "".join(text_deltas).strip()
        if message_text:
            output.append(
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": message_text}],
                }
            )
        return output

    def _event_to_dict(self, event: object) -> dict[str, object]:
        payload = self._coerce_optional_dict(event)
        if payload is not None:
            return payload

        event_type = getattr(event, "type", None)
        if isinstance(event_type, str):
            return {"type": event_type}
        return {}

    def _coerce_optional_dict(self, value: object) -> dict[str, object] | None:
        if isinstance(value, dict):
            return cast(dict[str, object], value)

        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="python")
            if isinstance(dumped, dict):
                return cast(dict[str, object], dumped)

        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            dumped = to_dict()
            if isinstance(dumped, dict):
                return cast(dict[str, object], dumped)

        return None

    def _normalize_response_payload(
        self, response: dict[str, object]
    ) -> dict[str, object]:
        nested_response = self._coerce_optional_dict(response.get("response"))
        normalized = nested_response if nested_response is not None else dict(response)

        output_text = normalized.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            normalized["output_text"] = output_text.strip()
            return normalized

        extracted = self._extract_assistant_text(normalized)
        if extracted:
            normalized["output_text"] = extracted

        return normalized

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
        raise LlmClientError(f"Agent state is missing required field: {key}")


def build_agent(
    *,
    llm_client: LlmClient,
    dataset_service: DatasetService,
    analysis_service: AnalysisService,
) -> Agent:
    return Agent(
        llm_client=llm_client,
        dataset_service=dataset_service,
        analysis_service=analysis_service,
    )
