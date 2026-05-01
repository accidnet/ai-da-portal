from collections.abc import Callable

from pydantic import BaseModel

from infrastructure.ai.client import coerce_optional_dict
from infrastructure.ai.streaming_events import RESPONSE_STREAMING_EVENTS

type ResponseNormalizer = Callable[[dict[str, object]], dict[str, object]]


class StreamEventResult(BaseModel):
    yielded_event: dict[str, object] | None = None
    completed_response: dict[str, object] | None = None


def handle_stream_event(
    *,
    payload: dict[str, object],
    response_id: str | None,
    function_calls: dict[str, dict[str, object]],
    text_deltas: list[str],
    normalize_response_payload: ResponseNormalizer,
) -> StreamEventResult:
    event_type = payload.get("type")
    handler = _build_handler_map(
        payload=payload,
        response_id=response_id,
        function_calls=function_calls,
        text_deltas=text_deltas,
        normalize_response_payload=normalize_response_payload,
    ).get(event_type)
    if handler is not None:
        return handler()

    return StreamEventResult()


def _build_handler_map(
    *,
    payload: dict[str, object],
    response_id: str | None,
    function_calls: dict[str, dict[str, object]],
    text_deltas: list[str],
    normalize_response_payload: ResponseNormalizer,
) -> dict[object, Callable[[], StreamEventResult]]:
    handlers: dict[object, Callable[[], StreamEventResult]] = {
        RESPONSE_STREAMING_EVENTS.response.output_text.delta: lambda: _handle_output_text_delta(
            payload, response_id, text_deltas
        ),
        RESPONSE_STREAMING_EVENTS.message.delta: lambda: _handle_output_text_delta(
            payload, response_id, text_deltas
        ),
        RESPONSE_STREAMING_EVENTS.response.output_item.added: lambda: _handle_output_item_add(
            payload,
            function_calls,
        ),
        RESPONSE_STREAMING_EVENTS.response.output_item.done: lambda: _handle_output_item_done(
            payload,
            function_calls,
        ),
        RESPONSE_STREAMING_EVENTS.response.function_call_arguments.delta: lambda: _handle_function_call_arguments_delta(
            payload, function_calls
        ),
        RESPONSE_STREAMING_EVENTS.response.function_call_arguments.done: lambda: _handle_function_call_arguments_done(
            payload, function_calls
        ),
    }
    response_payload = coerce_optional_dict(payload.get("response"))
    if response_payload is not None:
        handlers[RESPONSE_STREAMING_EVENTS.response.completed] = (
            lambda: _handle_response_completed(
                response_payload, normalize_response_payload
            )
        )
    return handlers


def _handle_response_completed(
    response_payload: dict[str, object],
    normalize_response_payload: ResponseNormalizer,
) -> StreamEventResult:
    return StreamEventResult(
        completed_response=normalize_response_payload(response_payload),
    )


def _handle_output_text_delta(
    payload: dict[str, object],
    response_id: str | None,
    text_deltas: list[str],
) -> StreamEventResult:
    delta = payload.get("delta") or payload.get("text")
    if isinstance(delta, str) and delta:
        text_deltas.append(delta)
        return StreamEventResult(
            yielded_event={
                "type": RESPONSE_STREAMING_EVENTS.response.output_text.delta,
                "delta": delta,
                "response_id": response_id,
            },
        )

    return StreamEventResult()


def _handle_output_item_add(
    payload: dict[str, object],
    function_calls: dict[str, dict[str, object]],
) -> StreamEventResult:
    item = coerce_optional_dict(payload.get("item"))
    if item is not None:
        _collect_stream_function_call(function_calls, item)

    return StreamEventResult()


def _handle_output_item_done(
    payload: dict[str, object],
    function_calls: dict[str, dict[str, object]],
) -> StreamEventResult:
    item = coerce_optional_dict(payload.get("item"))
    if item is not None:
        _collect_stream_function_call(function_calls, item)

    return StreamEventResult()


def _handle_function_call_arguments_delta(
    payload: dict[str, object],
    function_calls: dict[str, dict[str, object]],
) -> StreamEventResult:
    _append_function_call_arguments(function_calls, payload)
    return StreamEventResult()


def _handle_function_call_arguments_done(
    payload: dict[str, object],
    function_calls: dict[str, dict[str, object]],
) -> StreamEventResult:
    _append_function_call_arguments(function_calls, payload)
    return StreamEventResult()


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
