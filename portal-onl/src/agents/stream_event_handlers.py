from collections.abc import Callable

from pydantic import BaseModel

from core.sse import SseEvent
from infrastructure.ai.client import coerce_optional_dict
from infrastructure.ai.input_models import (
    ResponseOutputMessage,
    ResponseOutputText,
    FunctionCall,
)
from infrastructure.ai.streaming_events import RESPONSE_STREAMING_EVENTS

type ResponseNormalizer = Callable[[dict[str, object]], dict[str, object]]
type StreamEventHandler = Callable[[dict[str, object]], "ProcessedStreamEvent"]


class ProcessedStreamEvent(BaseModel):
    """원본 스트림 이벤트 처리 후 전달할 후속 데이터를 담습니다."""

    yielded_event: SseEvent | None = None
    input_item: ResponseOutputMessage | None = None
    function_call_item: dict[str, object] | None = None


def handle_stream_event(
    *,
    payload: dict[str, object],
    function_calls: dict[str, dict[str, object]],
    normalize_response_payload: ResponseNormalizer,
) -> ProcessedStreamEvent:
    """스트림 이벤트 타입에 맞는 처리 결과를 반환합니다."""
    event_type = payload.get("type")

    if event_type not in [
        # RESPONSE_STREAMING_EVENTS.response.completed,
        RESPONSE_STREAMING_EVENTS.response.in_progress,
        RESPONSE_STREAMING_EVENTS.response.created,
        RESPONSE_STREAMING_EVENTS.response.function_call_arguments.delta,
    ]:
        from pprint import pprint

        pprint(payload)

    handler = _STREAM_EVENT_HANDLERS.get(event_type)
    if handler is None:
        return ProcessedStreamEvent()

    processed_event = handler(payload)
    if processed_event.function_call_item is not None:
        _collect_stream_function_call(
            function_calls, processed_event.function_call_item
        )

    if processed_event.function_call_arguments_event is not None:
        _append_function_call_arguments(
            function_calls,
            processed_event.function_call_arguments_event,
        )

    return processed_event


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
    if item.get("type") == "function_call":
        return ProcessedStreamEvent(input_item=FunctionCall.model_validate(item))
    return ProcessedStreamEvent()


def _handle_response_completed(
    payload: dict[str, object],
) -> ProcessedStreamEvent:
    """완료 응답 payload를 정규화 전 상태로 추출합니다."""
    response_payload = coerce_optional_dict(payload.get("response"))
    if response_payload is None:
        return ProcessedStreamEvent()

    return ProcessedStreamEvent(
        completed_response=response_payload,
    )


_STREAM_EVENT_HANDLERS: dict[object, StreamEventHandler] = {
    RESPONSE_STREAMING_EVENTS.response.output_text.delta: _handle_output_text_delta,
    RESPONSE_STREAMING_EVENTS.response.output_text.done: _handle_output_text_done,
    RESPONSE_STREAMING_EVENTS.message.delta: _handle_output_message_delta,
    RESPONSE_STREAMING_EVENTS.response.output_item.done: _handle_output_item_done,
    RESPONSE_STREAMING_EVENTS.response.completed: _handle_response_completed,
}


def _collect_stream_function_call(
    function_calls: dict[str, dict[str, object]], item: dict[str, object]
) -> None:
    if item.get("type") != "function_call":
        return

    item_id = _read_string(item.get("id"))
    call_id = _read_string(item.get("call_id"))
    lookup_key = call_id or item_id
    if lookup_key is None:
        return

    entry = function_calls.get(lookup_key)
    if entry is None:
        entry = {
            "type": "function_call",
            "arguments": "",
        }
        function_calls[lookup_key] = entry

    if item_id:
        entry["id"] = item_id
        function_calls[item_id] = entry
    if call_id:
        entry["call_id"] = call_id
        function_calls[call_id] = entry
    name = _read_string(item.get("name"))
    if name:
        entry["name"] = name

    arguments = item.get("arguments")
    if isinstance(arguments, str):
        entry["arguments"] = arguments

    status = _read_string(item.get("status"))
    if status:
        entry["status"] = status


def _append_function_call_arguments(
    function_calls: dict[str, dict[str, object]], event: dict[str, object]
) -> dict[str, object] | None:
    item_id = _read_string(event.get("item_id"))
    call_id = _read_string(event.get("call_id"))
    lookup_key = item_id or call_id
    if lookup_key is None:
        return None

    entry = function_calls.get(lookup_key)
    if entry is None:
        entry = {
            "type": "function_call",
            "arguments": "",
        }
        function_calls[lookup_key] = entry

    if item_id:
        entry["id"] = item_id
        function_calls[item_id] = entry
    if call_id:
        entry["call_id"] = call_id
        function_calls[call_id] = entry
    name = _read_string(event.get("name"))
    if name:
        entry["name"] = name

    delta = event.get("delta")
    arguments = event.get("arguments")
    if isinstance(delta, str):
        entry["arguments"] = f'{entry.get("arguments", "")}{delta}'
    elif isinstance(arguments, str):
        entry["arguments"] = arguments

    streamed_event: dict[str, object] = {
        "type": event.get("type"),
        "call_id": entry.get("call_id"),
        "item_id": entry.get("id"),
        "name": entry.get("name") or None,
        "response_id": event.get("response_id"),
    }
    if (
        event.get("type")
        == RESPONSE_STREAMING_EVENTS.response.function_call_arguments.delta
    ):
        streamed_event["delta"] = delta if isinstance(delta, str) else ""
    else:
        streamed_event["arguments"] = (
            entry.get("arguments") if isinstance(entry.get("arguments"), str) else ""
        )
    return streamed_event


def _read_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
