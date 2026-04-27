import logging
from collections.abc import Generator
from typing import cast

from agents.runtimes.base import BaseAgent
from agents.state import AgentState
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from infrastructure.llm.client import LlmClient
from tools.function_call_runtime import resolve_output_item_function_call


logger = logging.getLogger(__name__)


class ChatStreamingAgent(BaseAgent):
    def invoke(
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

            stream_function_call_items: list[dict[str, object]] = []
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
                    # 스트리밍 완료 이벤트에서 받은 function_call 원본도 다음 input에 함께 누적합니다.
                    stream_function_call_items.append(dict(item))
                    stream_tool_outputs.append(function_call_output)
                return stream_event

            response_kwargs = self._response_kwargs(next_input)

            response = yield from self._stream_response_payload(
                self._llm_client.create_response(**response_kwargs),
                handle_output_item_function_call=on_output_item_function_call,
            )

            response_id = response.get("id")
            if isinstance(response_id, str) and response_id:
                working_state["response_id"] = response_id

            if stream_tool_outputs:
                next_input = [
                    *next_input,
                    *self._response_output_to_input_items(
                        {"output": stream_function_call_items}
                    ),
                    *stream_tool_outputs,
                ]
                continue

            assistant_message = self._extract_assistant_text(response)
            if assistant_message:
                working_state["assistant_message"] = assistant_message
                working_state["status"] = "completed"
                working_state.setdefault("route", "conversation")
                return working_state

        working_state.setdefault("route", "conversation")
        return working_state


def build_chat_streaming_agent(
    *,
    llm_client: LlmClient,
    dataset_service: DatasetService,
    analysis_service: AnalysisService,
) -> ChatStreamingAgent:
    return ChatStreamingAgent(
        llm_client=llm_client,
        dataset_service=dataset_service,
        analysis_service=analysis_service,
    )
