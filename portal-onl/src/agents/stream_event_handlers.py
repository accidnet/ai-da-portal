from collections.abc import Callable

from pydantic import BaseModel

from core.sse import SseEvent
from infrastructure.ai.client import coerce_optional_dict
from infrastructure.ai.input_models import (
    FunctionCall,
    ResponseOutputMessage,
    ResponseOutputText,
)
from infrastructure.ai.streaming_events import RESPONSE_STREAMING_EVENTS

type StreamEventHandler = Callable[[dict[str, object]], "ProcessedStreamEvent"]


class ProcessedStreamEvent(BaseModel):
    """원본 스트림 이벤트 처리 후 전달할 후속 데이터를 담습니다."""

    yielded_event: SseEvent | None = None
    input_item: ResponseOutputMessage | FunctionCall | None = None
    function_call_item: FunctionCall | None = None


def handle_stream_event(payload: dict[str, object]) -> ProcessedStreamEvent:
    """스트림 이벤트 타입에 맞는 처리 결과를 반환합니다."""
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


def _handle_output_text_done(
    payload: dict[str, object],
) -> ProcessedStreamEvent:
    """완료된 텍스트가 있으면 assistant 본문 후보로 보관합니다."""
    item_id = payload.get("item_id")
    text = payload.get("text")
    if isinstance(text, str) and text:
        return ProcessedStreamEvent(
            input_item=ResponseOutputMessage(
                id=item_id if isinstance(item_id, str) else None,
                content=(ResponseOutputText(text=text),),
            )
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
    """완료된 output item 중 function call 후보를 추출합니다."""
    item = coerce_optional_dict(payload.get("item"))
    if item is not None and item.get("type") == "function_call":
        function_call = FunctionCall.model_validate(item)
        return ProcessedStreamEvent(
            input_item=function_call,
            function_call_item=function_call,
        )
    return ProcessedStreamEvent()


def _handle_response_completed(
    payload: dict[str, object],
) -> ProcessedStreamEvent:
    """완료 이벤트는 개별 done 이벤트에서 수집한 입력만 사용하므로 무시합니다."""
    return ProcessedStreamEvent()


_STREAM_EVENT_HANDLERS: dict[object, StreamEventHandler] = {
    RESPONSE_STREAMING_EVENTS.response.output_text.delta: _handle_output_text_delta,
    RESPONSE_STREAMING_EVENTS.response.output_text.done: _handle_output_text_done,
    RESPONSE_STREAMING_EVENTS.message.delta: _handle_output_message_delta,
    RESPONSE_STREAMING_EVENTS.response.output_item.done: _handle_output_item_done,
    RESPONSE_STREAMING_EVENTS.response.completed: _handle_response_completed,
}
