import json
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from typing import Literal, cast

from agents.prompt_loader import load_prompt
from agents.state import AgentState, AgentStateSnapshot, AgentRoute, PlanStep
from domain.analyses.schemas import AnalysisRequest
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from domain.shared import AnalyticsPayload, WorkspacePayload
from infrastructure.llm.client import LlmClient, LlmClientError
from infrastructure.llm.streaming_events import RESPONSE_STREAMING_EVENTS
from tools import registry, update_plan


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
                    instructions=self._system_prompt(),
                    previous_response_id=working_state.get("response_id"),
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
                    {
                        "type": "function_call_output",
                        "call_id": function_call.call_id,
                        "output": json.dumps(
                            self._execute_function_call(working_state, function_call),
                            ensure_ascii=False,
                        ),
                    }
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
        print("[TMP-INPUT]")
        print(next_input)

        # TODO: 개발중에만 일시적으로 정해두고, 이후에는 사용자 설정에서 가능하도록 할 예정.
        max_iterations = 3
        iteration_count = 0

        while True:
            if iteration_count >= max_iterations:
                break
            iteration_count += 1

            response_kwargs: dict[str, object] = {
                "previous_response_id": working_state.get("response_id"),
                "input": next_input,
                "tools": registry.get_tool_definitions(),
                "tool_choice": "auto",
                "parallel_tool_calls": False,
                "reasoning": {"effort": "medium"},
                "max_output_tokens": 900,
            }
            if iteration_count == 1:
                response_kwargs["instructions"] = self._system_prompt()

            response = yield from self._stream_response_payload(
                self._llm_client.create_response(**response_kwargs)
            )

            response_id = response.get("id")
            if isinstance(response_id, str) and response_id:
                working_state["response_id"] = response_id

            function_calls = self._extract_function_calls(response)
            if function_calls:
                tool_outputs: list[dict[str, object]] = []
                for function_call in function_calls:
                    tool_result = self._execute_function_call(
                        working_state, function_call
                    )
                    tool_outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": function_call.call_id,
                            "output": json.dumps(tool_result, ensure_ascii=False),
                        }
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

    def _system_prompt(self) -> str:
        return load_prompt("base.md")

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
        return [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": "다음의 정보를 활용하세요.\n"
                        + (json.dumps(payload, ensure_ascii=False)),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": self._require_string(state, "message"),
                    }
                ],
            },
        ]

    def _execute_function_call(
        self, state: AgentState, function_call: _FunctionCall
    ) -> dict[str, object]:
        state["used_tools"] = [*state.get("used_tools", []), function_call.name]
        if function_call.name == "update_plan":
            return update_plan.execute(state, function_call.arguments)
        if function_call.name == "inspect_dataset_context":
            state["route"] = "dataset_analysis"
            state["status"] = "profiling"
            return self._inspect_dataset_context(state, function_call.arguments)
        if function_call.name == "run_portal_analysis":
            state["status"] = "running_analysis"
            return self._run_portal_analysis(state, function_call.arguments)
        if function_call.name == "load_uploaded_dataset_file":
            return self._load_uploaded_dataset_file(function_call.arguments)
        return {"ok": False, "error": f"Unsupported tool: {function_call.name}"}

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

    def _inspect_dataset_context(
        self, state: AgentState, arguments: dict[str, object]
    ) -> dict[str, object]:
        dataset_id = self._resolve_dataset_id(
            state=state,
            preferred_dataset_id=self._read_string(arguments.get("dataset_id")),
        )
        if dataset_id is None:
            return {
                "ok": False,
                "error": "No dataset is available.",
                "available_dataset_ids": self._available_dataset_ids(state),
            }

        include_preview = self._read_bool(
            arguments.get("include_preview"), default=True
        )
        include_profile = self._read_bool(
            arguments.get("include_profile"), default=True
        )
        payload: dict[str, object] = {
            "ok": True,
            "dataset_id": dataset_id,
            "available_dataset_ids": self._available_dataset_ids(state),
        }
        if include_profile:
            payload["profile"] = self._dataset_service.get_profile(
                dataset_id
            ).model_dump(mode="json")
        if include_preview:
            payload["preview"] = self._dataset_service.get_preview(
                dataset_id
            ).model_dump(mode="json")
        state["resolved_dataset_id"] = dataset_id
        return payload

    def _run_portal_analysis(
        self, state: AgentState, arguments: dict[str, object]
    ) -> dict[str, object]:
        route = self._read_string(arguments.get("route")) or "analysis_request"
        analysis_type = self._read_string(arguments.get("analysis_type"))
        dataset_id = self._resolve_dataset_id(
            state=state,
            preferred_dataset_id=self._read_string(arguments.get("dataset_id")),
        )
        if dataset_id is None:
            return {
                "ok": False,
                "route": route,
                "analysis_type": analysis_type,
                "error": "No dataset is available for analysis.",
                "available_dataset_ids": self._available_dataset_ids(state),
            }
        if analysis_type is None:
            return {
                "ok": False,
                "route": route,
                "error": "analysis_type is required.",
            }

        resolved_analysis_type = cast(
            Literal[
                "dataset_profile",
                "descriptive_summary",
                "correlation",
                "trend",
                "grouped_aggregation",
                "anomaly_detection",
            ],
            analysis_type,
        )
        prompt = self._read_string(arguments.get("prompt")) or self._require_string(
            state, "message"
        )
        detail = self._analysis_service.create(
            AnalysisRequest(
                session_id=self._require_string(state, "session_id"),
                dataset_id=dataset_id,
                analysis_type=resolved_analysis_type,
                prompt=prompt,
            )
        )
        state["route"] = route  # type: ignore[assignment]
        state["analysis_type"] = analysis_type
        state["resolved_dataset_id"] = dataset_id
        state["analytics"] = detail.analytics
        state["workspace"] = detail.workspace

        analytics = detail.analytics
        workspace = detail.workspace
        return {
            "ok": True,
            "route": route,
            "analysis_type": analysis_type,
            "dataset_id": dataset_id,
            "analysis_id": detail.id,
            "summary_cards": (
                [card.model_dump(mode="json") for card in analytics.summary_cards[:4]]
                if analytics is not None
                else []
            ),
            "chart_titles": (
                [chart.title for chart in analytics.charts[:3]]
                if analytics is not None
                else []
            ),
            "table_titles": (
                [table.title for table in analytics.tables[:2]]
                if analytics is not None
                else []
            ),
            "insights": (
                [insight.model_dump(mode="json") for insight in analytics.insights[:3]]
                if analytics is not None
                else []
            ),
            "workspace": workspace.model_dump(mode="json") if workspace else None,
        }

    def _load_uploaded_dataset_file(
        self, arguments: dict[str, object]
    ) -> dict[str, object]:
        filename = self._read_string(arguments.get("filename"))
        if filename is None:
            return {"ok": False, "error": "filename is required."}

        try:
            payload = self._dataset_service.load_uploaded_file_by_filename(filename)
        except FileNotFoundError:
            return {
                "ok": False,
                "error": f"Uploaded file not found: {filename}",
            }
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        return {"ok": True, **payload}

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
        self, response: object
    ) -> Generator[dict[str, object], None, dict[str, object]]:
        payload = self._coerce_optional_dict(response)
        if payload is not None:
            return self._normalize_response_payload(payload)
        return (yield from self._parse_stream_response_events(response))

    def _parse_stream_response(self, stream: object) -> dict[str, object]:
        parser = self._parse_stream_response_events(stream)
        try:
            while True:
                next(parser)
        except StopIteration as stop:
            return stop.value

    def _parse_stream_response_events(
        self, stream: object
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

                result = self._handle_stream_event(
                    payload=payload,
                    response_id=response_id,
                    response_payload=response_payload,
                    function_calls=function_calls,
                    text_deltas=text_deltas,
                    final_text=final_text,
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

    def _handle_stream_event(
        self,
        *,
        payload: dict[str, object],
        response_id: str | None,
        response_payload: dict[str, object] | None,
        function_calls: dict[str, dict[str, object]],
        text_deltas: list[str],
        final_text: str | None,
    ) -> dict[str, object]:
        event_type = payload.get("type")

        # DEBUG를 위한 임시 출력
        if event_type not in (
            RESPONSE_STREAMING_EVENTS.response.created,
            RESPONSE_STREAMING_EVENTS.response.completed,
            RESPONSE_STREAMING_EVENTS.response.in_progress,
        ):
            from pprint import pprint

            pprint("[TMP-TYPE]")
            pprint(event_type)
            print("[TMP-PAYLOAD]")
            pprint(payload)
            print("==" * 60)

        if (
            event_type == RESPONSE_STREAMING_EVENTS.response.completed
            and response_payload is not None
        ):
            return {
                "handled": True,
                "yielded_event": None,
                "completed_response": self._normalize_response_payload(
                    response_payload
                ),
                "final_text": final_text,
            }

        if event_type in {
            RESPONSE_STREAMING_EVENTS.response.output_text.delta,
            RESPONSE_STREAMING_EVENTS.message.delta,
        }:
            delta = payload.get("delta") or payload.get("text")
            if isinstance(delta, str) and delta:
                text_deltas.append(delta)
                return {
                    "handled": True,
                    "yielded_event": {
                        "type": RESPONSE_STREAMING_EVENTS.response.output_text.delta,
                        "delta": delta,
                        "response_id": response_id,
                    },
                    "completed_response": None,
                    "final_text": final_text,
                }
            return {
                "handled": True,
                "yielded_event": None,
                "completed_response": None,
                "final_text": final_text,
            }

        if event_type in {
            RESPONSE_STREAMING_EVENTS.response.output_text.done,
            RESPONSE_STREAMING_EVENTS.message.completed,
        }:
            text = payload.get("text") or payload.get("delta")
            return {
                "handled": True,
                "yielded_event": None,
                "completed_response": None,
                "final_text": text.strip()
                if isinstance(text, str) and text.strip()
                else final_text,
            }

        if event_type in {
            RESPONSE_STREAMING_EVENTS.response.output_item.added,
            RESPONSE_STREAMING_EVENTS.response.output_item.done,
        }:
            item = self._coerce_optional_dict(payload.get("item"))
            if item is not None:
                self._collect_stream_function_call(function_calls, item)
            return {
                "handled": True,
                "yielded_event": None,
                "completed_response": None,
                "final_text": final_text,
            }

        if event_type in {
            RESPONSE_STREAMING_EVENTS.response.function_call_arguments.delta,
            RESPONSE_STREAMING_EVENTS.response.function_call_arguments.done,
        }:
            function_call_event = self._append_function_call_arguments(
                function_calls, payload
            )
            return {
                "handled": True,
                "yielded_event": function_call_event,
                "completed_response": None,
                "final_text": final_text,
            }

        return {
            "handled": False,
            "yielded_event": None,
            "completed_response": None,
            "final_text": final_text,
        }

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

    def _collect_stream_function_call(
        self, function_calls: dict[str, dict[str, object]], item: dict[str, object]
    ) -> None:
        if item.get("type") != "function_call":
            return

        call_id = self._read_string(item.get("call_id"))
        if call_id is None:
            return

        entry = function_calls.setdefault(
            call_id,
            {
                "type": "function_call",
                "call_id": call_id,
                "name": self._read_string(item.get("name")) or "",
                "arguments": "",
            },
        )

        name = self._read_string(item.get("name"))
        if name:
            entry["name"] = name

        arguments = item.get("arguments")
        if isinstance(arguments, str):
            entry["arguments"] = arguments

    def _append_function_call_arguments(
        self, function_calls: dict[str, dict[str, object]], event: dict[str, object]
    ) -> dict[str, object] | None:
        call_id = self._read_string(event.get("call_id")) or self._read_string(
            event.get("item_id")
        )
        if call_id is None:
            return None

        entry = function_calls.setdefault(
            call_id,
            {
                "type": "function_call",
                "call_id": call_id,
                "name": self._read_string(event.get("name")) or "",
                "arguments": "",
            },
        )

        name = self._read_string(event.get("name"))
        if name:
            entry["name"] = name

        delta = event.get("delta")
        arguments = event.get("arguments")
        if isinstance(delta, str):
            entry["arguments"] = f'{entry.get("arguments", "")}{delta}'
        elif isinstance(arguments, str):
            entry["arguments"] = arguments

        streamed_event = {
            "type": event.get("type"),
            "call_id": call_id,
            "name": entry.get("name") or None,
            "response_id": event.get("response_id"),
        }
        if event.get("type") == RESPONSE_STREAMING_EVENTS.response.function_call_arguments.delta:
            streamed_event["delta"] = delta if isinstance(delta, str) else ""
        else:
            streamed_event["arguments"] = (
                entry.get("arguments") if isinstance(entry.get("arguments"), str) else ""
            )
        return streamed_event

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
