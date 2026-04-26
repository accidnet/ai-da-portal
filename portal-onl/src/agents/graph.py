import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, cast

from agents.prompt_loader import load_prompt
from agents.state import AgentState
from domain.analyses.schemas import AnalysisRequest
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from infrastructure.llm.client import LlmClient, LlmClientError
from tools import update_plan


@dataclass(slots=True)
class _FunctionCall:
    call_id: str
    name: str
    arguments: dict[str, object]


class AgentGraph:
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

        max_iterations = 1
        iteration_count = 0
        next_input: list[dict[str, object]] = self._build_initial_input(working_state)

        while True:
            if iteration_count >= max_iterations:
                break
            iteration_count += 1

            response = self._llm_client.create_response(
                instructions=self._system_prompt(),
                previous_response_id=working_state.get("response_id"),
                input=next_input,
                tools=self._tool_definitions(),
                tool_choice="auto",
                parallel_tool_calls=False,
                reasoning={"effort": "medium"},
                max_output_tokens=900,
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
                working_state.setdefault("route", "conversation")
                break

            break

        working_state.setdefault("route", "conversation")
        return working_state

    def _system_prompt(self) -> str:
        return load_prompt("base.md")

    def _build_initial_input(self, state: AgentState) -> list[dict[str, object]]:
        payload = {
            "session_id": self._require_string(state, "session_id"),
            "message": self._require_string(state, "message"),
            "requested_dataset_ids": state.get("dataset_ids", []),
            "session_dataset_ids": state.get("session_dataset_ids", []),
            "latest_dataset_id": self._dataset_service.get_latest_dataset_id(),
            "routing_hints": {
                "direct_reply_examples": [
                    "안녕",
                    "상관분석이 뭐야?",
                    "방금 답변을 한 줄로 줄여줘",
                ],
                "inspect_dataset_context_examples": [
                    "업로드된 파일 컬럼을 설명해줘",
                    "결측치가 많은 열이 뭐야?",
                    "데이터 미리보기를 보여줘",
                ],
                "run_portal_analysis_examples": [
                    "매출 추세를 분석해줘",
                    "광고비와 전환의 상관관계를 보여줘",
                    "채널별 성과 비교 차트를 만들어줘",
                ],
            },
        }
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "라우팅 및 도구 계획 컨텍스트:\n"
                            + json.dumps(payload, ensure_ascii=False)
                        ),
                    }
                ],
            }
        ]

    def _tool_definitions(self) -> list[dict[str, object]]:
        return [
            update_plan.tool_definition(),
            {
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
            },
            {
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
            return self._inspect_dataset_context(state, function_call.arguments)
        if function_call.name == "run_portal_analysis":
            return self._run_portal_analysis(state, function_call.arguments)
        return {"ok": False, "error": f"Unsupported tool: {function_call.name}"}

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

    def _parse_stream_response(self, stream: object) -> dict[str, object]:
        response_id: str | None = None
        final_text: str | None = None
        text_deltas: list[str] = []
        function_calls: dict[str, dict[str, object]] = {}

        close = getattr(stream, "close", None)
        try:
            for event in cast(Iterable[object], stream):
                payload = self._event_to_dict(event)
                event_type = payload.get("type")

                response_payload = self._coerce_optional_dict(payload.get("response"))
                if response_payload is not None and response_id is None:
                    response_id = self._read_string(response_payload.get("id"))

                if event_type == "response.completed" and response_payload is not None:
                    return self._normalize_response_payload(response_payload)

                if event_type in {"response.output_text.delta", "message.delta"}:
                    delta = payload.get("delta") or payload.get("text")
                    if isinstance(delta, str) and delta:
                        text_deltas.append(delta)
                    continue

                if event_type in {"response.output_text.done", "message.completed"}:
                    text = payload.get("text") or payload.get("delta")
                    if isinstance(text, str) and text.strip():
                        final_text = text.strip()
                    continue

                if event_type in {
                    "response.output_item.added",
                    "response.output_item.done",
                }:
                    item = self._coerce_optional_dict(payload.get("item"))
                    if item is not None:
                        self._collect_stream_function_call(function_calls, item)
                    continue

                if event_type in {
                    "response.function_call_arguments.delta",
                    "response.function_call_arguments.done",
                }:
                    self._append_function_call_arguments(function_calls, payload)
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
    ) -> None:
        call_id = self._read_string(event.get("call_id")) or self._read_string(
            event.get("item_id")
        )
        if call_id is None:
            return

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

        arguments = event.get("delta") or event.get("arguments")
        if isinstance(arguments, str):
            entry["arguments"] = f'{entry.get("arguments", "")}{arguments}'

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


def build_agent_graph(
    *,
    llm_client: LlmClient,
    dataset_service: DatasetService,
    analysis_service: AnalysisService,
) -> AgentGraph:
    return AgentGraph(
        llm_client=llm_client,
        dataset_service=dataset_service,
        analysis_service=analysis_service,
    )
