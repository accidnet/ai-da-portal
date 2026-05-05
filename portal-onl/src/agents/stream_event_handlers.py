import json
from collections.abc import Callable

from pydantic import BaseModel

from core.sse import SseEvent
from infrastructure.ai.client import coerce_optional_dict
from shared.integrations.ai.contracts import (
    FunctionCall,
    ResponseOutputMessage,
)
from infrastructure.ai.streaming_events import RESPONSE_STREAMING_EVENTS

type StreamEventHandler = Callable[[dict[str, object]], "ProcessedStreamEvent"]


def _debug_stream_event(payload: dict[str, object]) -> None:
    """필요한 stream event payload를 로컬 디버깅용으로 출력합니다."""
    # 디버깅할 때만 True로 바꾸고, 보고 싶은 event type의 주석을 해제합니다.
    debug_enabled = False
    if not debug_enabled:
        return

    event_type = payload.get("type")
    debug_event_types = {
        # RESPONSE_STREAMING_EVENTS.response.created,
        # RESPONSE_STREAMING_EVENTS.response.in_progress,
        # RESPONSE_STREAMING_EVENTS.response.completed,
        RESPONSE_STREAMING_EVENTS.response.failed,
        RESPONSE_STREAMING_EVENTS.response.incomplete,
        RESPONSE_STREAMING_EVENTS.response.output_item.added,
        RESPONSE_STREAMING_EVENTS.response.output_item.done,
        RESPONSE_STREAMING_EVENTS.response.content_part.added,
        RESPONSE_STREAMING_EVENTS.response.content_part.done,
        # RESPONSE_STREAMING_EVENTS.response.output_text.delta,
        # RESPONSE_STREAMING_EVENTS.response.output_text.done,
        # RESPONSE_STREAMING_EVENTS.response.function_call_arguments.delta,
        RESPONSE_STREAMING_EVENTS.response.function_call_arguments.done,
        # RESPONSE_STREAMING_EVENTS.message.delta,
        RESPONSE_STREAMING_EVENTS.message.completed,
    }
    if event_type in debug_event_types:
        formatted_payload = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        print(f"[stream-event:{event_type}]\n{formatted_payload}")


class ProcessedStreamEvent(BaseModel):
    """원본 스트림 이벤트 처리 후 전달할 후속 데이터를 담습니다."""

    yielded_event: SseEvent | None = None
    input_item: ResponseOutputMessage | FunctionCall | None = None
    function_call_item: FunctionCall | None = None
    should_stop_iteration: bool = False


def handle_stream_event(payload: dict[str, object]) -> ProcessedStreamEvent:
    """스트림 이벤트 타입에 맞는 처리 결과를 반환합니다."""
    _debug_stream_event(payload)

    event_type = payload.get("type")
    handler = _STREAM_EVENT_HANDLERS.get(event_type)
    if handler is None:
        return ProcessedStreamEvent()

    return handler(payload)


def _handle_output_text_delta(
    payload: dict[str, object],
) -> ProcessedStreamEvent:
    """텍스트 delta 이벤트에서 프론트 전달 payload만 추출합니다."""
    delta = payload.get("delta")
    if isinstance(delta, str):
        return ProcessedStreamEvent(
            yielded_event=SseEvent(
                event_type=RESPONSE_STREAMING_EVENTS.response.output_text.delta,
                data={
                    "delta": delta,
                },
            ),
        )

    return ProcessedStreamEvent()


def _handle_output_message_delta(
    payload: dict[str, object],
) -> ProcessedStreamEvent:
    """텍스트 delta 이벤트에서 프론트 전달 payload만 추출합니다."""
    delta = payload.get("delta") or payload.get("text")
    if isinstance(delta, str) and delta:
        return ProcessedStreamEvent(
            yielded_event=SseEvent(
                event_type=RESPONSE_STREAMING_EVENTS.message.delta,
                data={
                    "delta": delta,
                },
            ),
        )

    return ProcessedStreamEvent()


def _handle_output_item_done(
    payload: dict[str, object],
) -> ProcessedStreamEvent:
    """완료된 output item에서 다음 input과 iteration 종료 후보를 추출합니다."""
    item = coerce_optional_dict(payload.get("item"))
    if item is not None and item.get("type") == "function_call":
        function_call = FunctionCall.model_validate(item)
        return ProcessedStreamEvent(
            input_item=function_call,
            function_call_item=function_call,
        )
    if item is not None and item.get("type") == "message":
        output_message = ResponseOutputMessage.model_validate(item)
        return ProcessedStreamEvent(
            input_item=output_message,
            should_stop_iteration=(
                output_message.status == "completed"
                and output_message.phase == "final_answer"
            ),
        )
    return ProcessedStreamEvent()


_STREAM_EVENT_HANDLERS: dict[object, StreamEventHandler] = {
    RESPONSE_STREAMING_EVENTS.response.output_text.delta: _handle_output_text_delta,
    RESPONSE_STREAMING_EVENTS.message.delta: _handle_output_message_delta,
    RESPONSE_STREAMING_EVENTS.response.output_item.done: _handle_output_item_done,
}
