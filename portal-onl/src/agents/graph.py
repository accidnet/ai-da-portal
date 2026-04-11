import json
from dataclasses import dataclass
from typing import Literal, cast

from agents.state import AgentState
from domain.analyses.schemas import AnalysisRequest
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from infrastructure.llm.client import LlmClient, LlmClientError


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

        response = self._llm_client.create_response(
            instructions=self._system_prompt(),
            input=self._build_initial_input(working_state),
            tools=self._tool_definitions(),
            tool_choice="auto",
            parallel_tool_calls=False,
            reasoning={"effort": "medium"},
            max_output_tokens=900,
        )

        for _ in range(6):
            response_id = response.get("id")
            if isinstance(response_id, str) and response_id:
                working_state["response_id"] = response_id

            function_calls = self._extract_function_calls(response)
            if function_calls:
                tool_outputs = [
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
                response = self._llm_client.create_response(
                    previous_response_id=working_state.get("response_id"),
                    input=tool_outputs,
                    tools=self._tool_definitions(),
                    tool_choice="auto",
                    parallel_tool_calls=False,
                    reasoning={"effort": "medium"},
                    max_output_tokens=900,
                )
                continue

            assistant_message = self._extract_assistant_text(response)
            if assistant_message:
                working_state["assistant_message"] = assistant_message
                working_state.setdefault("route", "conversation")
                return working_state

            break

        working_state.setdefault("route", "conversation")
        return working_state

    def _system_prompt(self) -> str:
        return (
            "You are the single orchestration LLM for a data analysis portal. "
            "Your job is to decide whether to continue reasoning privately, call a backend function, or answer the user directly. "
            "Decision policy: "
            "1) Respond directly without tools for greetings, UX guidance, conceptual explanations, follow-up wording changes, and general questions that do not require the portal's live dataset state. "
            "2) Use inspect_dataset_context when the user asks what data is attached, what columns exist, row or null coverage, schema meaning, preview rows, or whether a dataset is suitable before analysis. "
            "3) Use run_portal_analysis when the user asks for profiling, summary statistics, correlation, trend, forecasting, grouped comparison, anomaly detection, chart generation, or business interpretation grounded in uploaded data. "
            "4) If the user asks to continue from prior analytical context and a dataset is available, prefer run_portal_analysis over a generic answer. "
            "5) If no dataset is available for a data-grounded request, do not fabricate results; explain that the user should upload or attach a dataset. "
            "6) Usually call at most one function first; only call another function if the first result shows it is still needed. "
            "After tool results arrive, answer in concise Korean, explicitly tie claims to the returned tool output, and suggest the next useful analysis only when relevant."
        )

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
                            "Route and tool planning context:\n"
                            + json.dumps(payload, ensure_ascii=False)
                        ),
                    }
                ],
            }
        ]

    def _tool_definitions(self) -> list[dict[str, object]]:
        return [
            {
                "type": "function",
                "name": "inspect_dataset_context",
                "description": (
                    "Inspect an uploaded dataset profile and preview before answering questions about data structure, columns, quality, coverage, or available rows. Do not use this for actual analytical conclusions like correlation or trend analysis."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": ["string", "null"],
                            "description": "Specific dataset id to inspect. Use null to inspect the best available dataset.",
                        },
                        "include_preview": {
                            "type": "boolean",
                            "description": "Whether to include tabular preview rows.",
                            "default": True,
                        },
                        "include_profile": {
                            "type": "boolean",
                            "description": "Whether to include dataset profile statistics.",
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
                    "Run backend dataset profiling or analysis and return structured results for the final answer. Use this whenever the answer must be grounded in calculations or visual summaries from uploaded data."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "route": {
                            "type": "string",
                            "enum": ["dataset_analysis", "analysis_request"],
                            "description": "Use dataset_analysis for dataset overview/profile tasks, analysis_request for specific analytical questions.",
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
                            "description": "Backend analysis type to execute.",
                        },
                        "dataset_id": {
                            "type": ["string", "null"],
                            "description": "Specific dataset id to analyze. Use null to resolve automatically.",
                        },
                        "prompt": {
                            "type": ["string", "null"],
                            "description": "Optional focused prompt for the analysis request.",
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
