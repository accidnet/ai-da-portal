import json
import logging
from collections.abc import Generator, Iterable
from typing import cast

from agents.runtimes.base import BaseAgent
from agents.state import AgentState, PlanStep
from agents.stream_event_handlers import handle_stream_event
from core.sse import SseEvent
from application.datasets.service import DatasetApplicationService
from infrastructure.ai.client import AiClient, coerce_optional_dict
from infrastructure.ai.input_models import (
    FunctionCall,
    InputItemList,
    ResponseOutputMessage,
)

logger = logging.getLogger(__name__)
AgentStreamEvent = dict[str, object] | SseEvent


class ChatStreamingAgent(BaseAgent):
    """채팅 요청을 LLM 스트림과 tool 호출 이벤트로 실행하는 agent입니다."""

    def invoke(
        self, state: AgentState
    ) -> Generator[AgentStreamEvent, None, AgentState]:

        working_state = cast(AgentState, dict(state))
        working_state.setdefault("used_tools", [])
        working_state.setdefault("status", "queued")

        # 사용자 메세지를 포함하여 AI API input으로 사용하기 위한 빌드
        input_items = self._build_initial_inputs(
            message=self._require_string(working_state, "message"),
            dataset_ids=working_state.get("dataset_ids", []),
        )

        # TODO: 개발중에만 일시적으로 정해두고, 이후에는 사용자 설정에서 가능하도록 할 예정.
        max_iterations = 3
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
            stream_result = yield from self._parse_stream_events(
                self._llm_client.create_response(
                    **self._build_llm_request_kwargs(input_items),
                    stream=True,
                ),
            )

            # API 호출이 끝난 후 처리하는 로직
            new_input_items, state_event = self._handle_after_call_completion(
                working_state=working_state,
                stream_result=stream_result,
            )

            if state_event is not None:
                yield state_event

            # iteration이 끝날때마다 프론트에 전달
            yield SseEvent(
                event_type="agent.iteration.done",
                data={
                    "iteration": iteration_count,
                },
            )

            # iteration이 끝날때 새로운 input_items을 추가하여 멀티턴
            if new_input_items:
                input_items.extend(new_input_items)
                continue

        return working_state

    def _parse_stream_events(
        self, stream: object
    ) -> Generator[AgentStreamEvent, None, dict[str, object]]:
        """API 호출 1번 내에 발생하는 stream event에 대한 개별적 처리"""

        # streaming 중에 생성되는 input을 순차적으로 적재하여, 다음 step input에 추가하여 활용하기 위함
        input_items: list[ResponseOutputMessage | FunctionCall] = []
        function_call_items: list[FunctionCall] = []

        close = getattr(stream, "close", None)
        try:
            for event in cast(Iterable[object], stream):
                # TODO: 해당 부분은 AI Client 부분에서 처리되어서 넘어올수있게끔 가능한 지 확인 후 수정
                payload = coerce_optional_dict(event)

                if payload is None:
                    self._log_unhandled_stream_event(event)
                    continue

                # streaming의 각 type별로 처리
                processed_event = handle_stream_event(payload=payload)

                # 바로 프론트로 전달해야하는 경우
                yielded_event = processed_event.yielded_event
                if isinstance(yielded_event, SseEvent):
                    yield yielded_event

                # input에 넣을 item이 있을 경우 추가
                input_item = processed_event.input_item
                if input_item:
                    input_items.append(input_item)

                # 실행해야할 function call이 있을 경우 추가
                function_call_item = processed_event.function_call_item
                if function_call_item:
                    function_call_items.append(function_call_item)

        finally:
            if callable(close):
                close()

        return {"input_items": input_items, "function_call_items": function_call_items}

    def _log_unhandled_stream_event(self, event: object) -> None:
        if event is None or event == "" or event == [] or event == {}:
            return

        logger.warning(
            "Unhandled stream event payload type=%s value=%r",
            type(event).__name__,
            event,
        )

    def _handle_after_call_completion(
        self,
        *,
        working_state: AgentState,
        stream_result: dict[str, object],
    ) -> tuple[list[dict[str, object]] | None, SseEvent | None]:

        stream_input_items = cast(
            list[ResponseOutputMessage | FunctionCall],
            stream_result.get("input_items", []),
        )
        self._apply_assistant_message_to_state(working_state, stream_input_items)

        # 실행해야 할 function call이 있는 지 확인 후 실행
        function_call_items = cast(
            list[FunctionCall],
            stream_result.get("function_call_items", []),
        )
        self._apply_used_tools_to_state(working_state, function_call_items)
        function_call_outputs = self._execute_function_call_items(
            function_call_items=function_call_items,
        )
        state_event = None
        if function_call_outputs:
            # function call 중 update_plan은 프론트 상태 이벤트로도 전달합니다.
            update_plan_function_output = function_call_outputs.get("update_plan")
            if update_plan_function_output:
                self._apply_update_plan_output_to_state(
                    working_state, update_plan_function_output
                )
                state_event = SseEvent(
                    event_type="agent.state",
                    data=self._build_state_event(working_state),
                )
            new_input_items = [
                *InputItemList(items=tuple(stream_input_items)).to_payload(),
                *function_call_outputs.values(),
            ]
            return new_input_items, state_event

        return None, state_event

    def _apply_assistant_message_to_state(
        self,
        working_state: AgentState,
        input_items: list[ResponseOutputMessage | FunctionCall],
    ) -> None:
        """스트림에서 완료된 assistant message를 최종 state에 반영합니다."""
        text_parts: list[str] = []
        for input_item in input_items:
            if not isinstance(input_item, ResponseOutputMessage):
                continue
            for content in input_item.content:
                if content.text.strip():
                    text_parts.append(content.text.strip())

        if not text_parts:
            return

        working_state["assistant_message"] = "\n\n".join(text_parts)
        working_state["status"] = "completed"
        working_state.setdefault("route", "conversation")

    def _apply_used_tools_to_state(
        self,
        working_state: AgentState,
        function_call_items: list[FunctionCall],
    ) -> None:
        """실행된 function_call 이름을 최종 state에 누적합니다."""
        if not function_call_items:
            return

        used_tools = [
            tool for tool in working_state.get("used_tools", []) if isinstance(tool, str)
        ]
        for function_call in function_call_items:
            used_tools.append(function_call.name)
        working_state["used_tools"] = used_tools

    def _apply_update_plan_output_to_state(
        self,
        working_state: AgentState,
        function_call_output: dict[str, object],
    ) -> None:
        """update_plan function output의 JSON 문자열을 state plan으로 반영합니다."""
        output = function_call_output.get("output")
        if not isinstance(output, str):
            return

        try:
            tool_result = json.loads(output)
        except json.JSONDecodeError:
            return

        if not isinstance(tool_result, dict) or tool_result.get("ok") is not True:
            return

        raw_plan = tool_result.get("plan")
        if isinstance(raw_plan, list):
            working_state["plan"] = [
                cast(PlanStep, step)
                for step in raw_plan
                if isinstance(step, dict)
            ]
        explanation = tool_result.get("explanation")
        working_state["plan_explanation"] = (
            explanation.strip() if isinstance(explanation, str) else None
        )


def build_chat_streaming_agent(
    *,
    llm_client: AiClient,
    dataset_service: DatasetApplicationService,
) -> ChatStreamingAgent:
    """스트리밍 채팅 agent 인스턴스를 생성합니다."""
    return ChatStreamingAgent(
        llm_client=llm_client,
        dataset_service=dataset_service,
    )
