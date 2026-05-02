import logging
import json
from collections.abc import Generator, Iterable
from typing import cast

from agents.runtimes.base import BaseAgent
from agents.state import AgentState
from agents.stream_event_handlers import handle_stream_event
from core.sse import SseEvent
from domain.analyses.service import AnalysisService
from application.datasets.service import DatasetApplicationService
from infrastructure.ai.client import AiClient, coerce_optional_dict

logger = logging.getLogger(__name__)
AgentStreamEvent = dict[str, object] | SseEvent


class ChatStreamingAgent(BaseAgent):

    def invoke(
        self, state: AgentState
    ) -> Generator[AgentStreamEvent, None, AgentState]:

        working_state = cast(AgentState, dict(state))
        working_state.setdefault("used_tools", [])
        working_state.setdefault("status", "queued")
        last_state_fingerprint = json.dumps(
            self._build_state_event(working_state)["state"],
            ensure_ascii=False,
            sort_keys=True,
        )

        # 사용자 메세지를 포함하여 AI API input으로 사용하기 위한 빌드
        inputs = self._build_inputs(
            message=self._require_string(working_state, "message"),
            dataset_ids=working_state.get("dataset_ids", []),
        )

        # TODO: 개발중에만 일시적으로 정해두고, 이후에는 사용자 설정에서 가능하도록 할 예정.
        max_iterations = 10
        iteration_count = 0
        while True:

            if iteration_count >= max_iterations:
                break

            iteration_count += 1

            # iteration이 시작할때마다 프론트에 전달
            yield SseEvent(
                event_type="agent.iteration.start",
                data={
                    "iteration": iteration_count,
                },
            )

            # 외부 LLM API 호출
            response = yield from self._parse_stream_response_events(
                self._llm_client.create_response(
                    **self._build_llm_request_kwargs(inputs),
                    stream=True,
                ),
            )

            response_id = response.get("id")
            if isinstance(response_id, str) and response_id:
                working_state["response_id"] = response_id

            result_state, updated_input, state_event, last_state_fingerprint = (
                self._handle_after_call_completion(
                    working_state=working_state,
                    response=response,
                    next_input=inputs,
                    last_state_fingerprint=last_state_fingerprint,
                )
            )
            if state_event is not None:
                yield state_event
            if updated_input is not None:
                inputs = updated_input
                continue
            if result_state is not None:
                return result_state

        return working_state

    def _parse_stream_response_events(
        self, stream: object
    ) -> Generator[dict[str, object], None, dict[str, object]]:
        response_id: str | None = None
        text_deltas: list[str] = []
        function_calls: dict[str, dict[str, object]] = {}

        close = getattr(stream, "close", None)
        try:
            for event in cast(Iterable[object], stream):
                # TODO: 해당 부분은 AI Client 부분에서 처리되어서 넘어올수있게끔 가능한 지 확인 후 수정
                payload = coerce_optional_dict(event)

                if payload is None:
                    self._log_unhandled_stream_event(event)
                    continue

                response_payload = coerce_optional_dict(payload.get("response"))
                if response_payload is not None and response_id is None:
                    response_id = self._read_string(response_payload.get("id"))

                result = handle_stream_event(
                    payload=payload,
                    response_id=response_id,
                    function_calls=function_calls,
                    text_deltas=text_deltas,
                    normalize_response_payload=self._normalize_response_payload,
                )

                completed_response = result.completed_response
                if isinstance(completed_response, dict):
                    output = self._build_stream_output(
                        function_calls,
                        text_deltas,
                    )
                    return self._merge_stream_output(completed_response, output)

                yielded_event = result.yielded_event
                if isinstance(yielded_event, dict):
                    yield yielded_event
        finally:
            if callable(close):
                close()

        normalized: dict[str, object] = {}
        if response_id:
            normalized["id"] = response_id

        output = self._build_stream_output(function_calls, text_deltas)
        if output:
            normalized["output"] = output

        output_text = "".join(text_deltas).strip()
        if output_text:
            normalized["output_text"] = output_text

        return self._normalize_response_payload(normalized)

    def _log_unhandled_stream_event(self, event: object) -> None:
        if event is None or event == "" or event == [] or event == {}:
            return

        logger.warning(
            "Unhandled stream event payload type=%s value=%r",
            type(event).__name__,
            event,
        )

    def _merge_stream_output(
        self,
        response: dict[str, object],
        stream_output: list[dict[str, object]],
    ) -> dict[str, object]:
        if not stream_output:
            return self._normalize_response_payload(response)

        normalized = self._normalize_response_payload(response)
        output = normalized.get("output")
        if not isinstance(output, list) or not output:
            normalized["output"] = stream_output
            return self._normalize_response_payload(normalized)

        existing_call_ids = {
            item.get("call_id")
            for item in output
            if isinstance(item, dict) and item.get("type") == "function_call"
        }
        missing_stream_items = [
            item
            for item in stream_output
            if item.get("type") == "function_call"
            and item.get("call_id") not in existing_call_ids
        ]
        if missing_stream_items:
            normalized["output"] = [*output, *missing_stream_items]

        return self._normalize_response_payload(normalized)

    def _build_stream_output(
        self,
        function_calls: dict[str, dict[str, object]],
        text_deltas: list[str],
    ) -> list[dict[str, object]]:
        output: list[dict[str, object]] = []
        seen_call_ids: set[str] = set()
        for function_call in function_calls.values():
            call_id = self._read_string(function_call.get("call_id"))
            name = self._read_string(function_call.get("name"))
            if not call_id or not name or call_id in seen_call_ids:
                continue
            seen_call_ids.add(call_id)
            output.append(function_call)

        message_text = "".join(text_deltas).strip()
        if message_text:
            output.append(
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": message_text}],
                }
            )
        return output

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


def build_chat_streaming_agent(
    *,
    llm_client: AiClient,
    dataset_service: DatasetApplicationService,
    analysis_service: AnalysisService,
) -> ChatStreamingAgent:
    return ChatStreamingAgent(
        llm_client=llm_client,
        dataset_service=dataset_service,
        analysis_service=analysis_service,
    )
