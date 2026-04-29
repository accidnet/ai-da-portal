import logging
import json
from collections.abc import Generator
from typing import cast

from agents.runtimes.base import BaseAgent
from agents.state import AgentState
from domain.analyses.service import AnalysisService
from domain.datasets.service import DatasetService
from infrastructure.llm.client import LlmClient

logger = logging.getLogger(__name__)


class ChatStreamingAgent(BaseAgent):
    def _handle_after_call_completion(
        self,
        *,
        working_state: AgentState,
        response: dict[str, object],
        next_input: list[dict[str, object]],
        last_state_fingerprint: str,
    ) -> tuple[
        AgentState | None,
        list[dict[str, object]] | None,
        dict[str, object] | None,
        str,
    ]:
        # 스트림 완료 후 응답 내용을 기준으로 다음 액션을 결정합니다.
        tool_outputs = self._execute_response_function_calls(working_state, response)
        if tool_outputs:
            state_event = self._build_state_event(working_state)
            state_fingerprint = json.dumps(
                state_event["state"],
                ensure_ascii=False,
                sort_keys=True,
            )
            if state_fingerprint == last_state_fingerprint:
                state_event = None
            else:
                last_state_fingerprint = state_fingerprint

            next_input = self._extend_input_with_response(
                next_input,
                response,
                tool_outputs=tool_outputs,
            )
            return None, next_input, state_event, last_state_fingerprint

        assistant_message = self._extract_assistant_text(response)
        if assistant_message:
            working_state["assistant_message"] = assistant_message
            working_state["status"] = "completed"
            working_state.setdefault("route", "conversation")
            return working_state, None, None, last_state_fingerprint

        return None, None, None, last_state_fingerprint

    def invoke(
        self, state: AgentState
    ) -> Generator[dict[str, object], None, AgentState]:
        working_state = cast(AgentState, dict(state))
        working_state.setdefault("used_tools", [])
        working_state.setdefault("status", "queued")
        last_state_fingerprint = json.dumps(
            self._build_state_event(working_state)["state"],
            ensure_ascii=False,
            sort_keys=True,
        )
        next_input = self._build_initial_input(working_state)
        logger.debug("Agent stream input prepared next_input=%s", next_input)

        # TODO: 개발중에만 일시적으로 정해두고, 이후에는 사용자 설정에서 가능하도록 할 예정.
        max_iterations = 10
        iteration_count = 0

        while True:
            logger.debug(f"Iteration {iteration_count}.")
            if iteration_count >= max_iterations:
                break
            iteration_count += 1

            response_kwargs = self._response_kwargs(next_input)
            if iteration_count > 1:
                yield {
                    "type": "agent.text_segment.start",
                    "iteration": iteration_count,
                }

            response = yield from self._stream_response_payload(
                self._llm_client.create_response(**response_kwargs),
            )

            response_id = response.get("id")
            if isinstance(response_id, str) and response_id:
                working_state["response_id"] = response_id

            result_state, updated_input, state_event, last_state_fingerprint = (
                self._handle_after_call_completion(
                    working_state=working_state,
                    response=response,
                    next_input=next_input,
                    last_state_fingerprint=last_state_fingerprint,
                )
            )
            if state_event is not None:
                yield state_event
            if updated_input is not None:
                next_input = updated_input
                continue
            if result_state is not None:
                return result_state

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
