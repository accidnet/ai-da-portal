from collections.abc import Callable

from infrastructure.llm.streaming_events import RESPONSE_STREAMING_EVENTS


type StreamEventResult = dict[str, object]
type DictCoercer = Callable[[object], dict[str, object] | None]
type ResponseNormalizer = Callable[[dict[str, object]], dict[str, object]]
type OutputItemFunctionCallHandler = Callable[[dict[str, object]], dict[str, object] | None]


QUIET_EVENT_TYPES = {
    RESPONSE_STREAMING_EVENTS.response.created,
    RESPONSE_STREAMING_EVENTS.response.completed,
    RESPONSE_STREAMING_EVENTS.response.in_progress,
    RESPONSE_STREAMING_EVENTS.response.function_call_arguments.delta,
}


def handle_stream_event(
    *,
    payload: dict[str, object],
    response_id: str | None,
    response_payload: dict[str, object] | None,
    function_calls: dict[str, dict[str, object]],
    text_deltas: list[str],
    final_text: str | None,
    coerce_optional_dict: DictCoercer,
    normalize_response_payload: ResponseNormalizer,
    handle_output_item_function_call: OutputItemFunctionCallHandler | None = None,
) -> StreamEventResult:
    event_type = payload.get("type")

    _debug_stream_event(event_type, payload)

    handler = _build_handler_map(
        payload=payload,
        response_payload=response_payload,
        response_id=response_id,
        function_calls=function_calls,
        text_deltas=text_deltas,
        final_text=final_text,
        coerce_optional_dict=coerce_optional_dict,
        normalize_response_payload=normalize_response_payload,
        handle_output_item_function_call=handle_output_item_function_call,
    ).get(event_type)
    if handler is not None:
        return handler()

    return _build_result(
        handled=False,
        yielded_event=None,
        completed_response=None,
        final_text=final_text,
    )


def _build_handler_map(
    *,
    payload: dict[str, object],
    response_payload: dict[str, object] | None,
    response_id: str | None,
    function_calls: dict[str, dict[str, object]],
    text_deltas: list[str],
    final_text: str | None,
    coerce_optional_dict: DictCoercer,
    normalize_response_payload: ResponseNormalizer,
    handle_output_item_function_call: OutputItemFunctionCallHandler | None,
) -> dict[object, Callable[[], StreamEventResult]]:
    handlers: dict[object, Callable[[], StreamEventResult]] = {
        RESPONSE_STREAMING_EVENTS.response.output_text.delta: lambda: _handle_output_text_delta(
            payload, response_id, text_deltas, final_text
        ),
        RESPONSE_STREAMING_EVENTS.message.delta: lambda: _handle_output_text_delta(
            payload, response_id, text_deltas, final_text
        ),
        RESPONSE_STREAMING_EVENTS.response.output_text.done: lambda: _handle_output_text_done(
            payload, final_text
        ),
        RESPONSE_STREAMING_EVENTS.message.completed: lambda: _handle_output_text_done(
            payload, final_text
        ),
        RESPONSE_STREAMING_EVENTS.response.output_item.added: lambda: _handle_output_item(
            payload,
            function_calls,
            final_text,
            coerce_optional_dict,
        ),
        RESPONSE_STREAMING_EVENTS.response.output_item.done: lambda: _handle_output_item_done(
            payload,
            function_calls,
            final_text,
            coerce_optional_dict,
            handle_output_item_function_call,
        ),
        RESPONSE_STREAMING_EVENTS.response.function_call_arguments.delta: lambda: _handle_function_call_arguments_delta(
            payload, function_calls, final_text
        ),
        RESPONSE_STREAMING_EVENTS.response.function_call_arguments.done: lambda: _handle_function_call_arguments_done(
            payload, function_calls, final_text
        ),
    }
    if response_payload is not None:
        handlers[RESPONSE_STREAMING_EVENTS.response.completed] = (
            lambda: _handle_response_completed(
                response_payload, final_text, normalize_response_payload
            )
        )
    return handlers


def _debug_stream_event(event_type: object, payload: dict[str, object]) -> None:
    if event_type in QUIET_EVENT_TYPES:
        return

    from pprint import pprint

    pprint("[TMP-TYPE]")
    pprint(event_type)
    print("[TMP-PAYLOAD]")
    pprint(payload)
    print("==" * 60)


def _handle_response_completed(
    response_payload: dict[str, object],
    final_text: str | None,
    normalize_response_payload: ResponseNormalizer,
) -> StreamEventResult:
    return _build_result(
        handled=True,
        yielded_event=None,
        completed_response=normalize_response_payload(response_payload),
        final_text=final_text,
    )


def _handle_output_text_delta(
    payload: dict[str, object],
    response_id: str | None,
    text_deltas: list[str],
    final_text: str | None,
) -> StreamEventResult:
    delta = payload.get("delta") or payload.get("text")
    if isinstance(delta, str) and delta:
        text_deltas.append(delta)
        return _build_result(
            handled=True,
            yielded_event={
                "type": RESPONSE_STREAMING_EVENTS.response.output_text.delta,
                "delta": delta,
                "response_id": response_id,
            },
            completed_response=None,
            final_text=final_text,
        )

    return _build_result(
        handled=True,
        yielded_event=None,
        completed_response=None,
        final_text=final_text,
    )


def _handle_output_text_done(
    payload: dict[str, object],
    final_text: str | None,
) -> StreamEventResult:
    text = payload.get("text") or payload.get("delta")
    return _build_result(
        handled=True,
        yielded_event=None,
        completed_response=None,
        final_text=(
            text.strip() if isinstance(text, str) and text.strip() else final_text
        ),
    )


def _handle_output_item(
    payload: dict[str, object],
    function_calls: dict[str, dict[str, object]],
    final_text: str | None,
    coerce_optional_dict: DictCoercer,
) -> StreamEventResult:
    item = coerce_optional_dict(payload.get("item"))
    if item is not None:
        _collect_stream_function_call(function_calls, item)

    return _build_result(
        handled=True,
        yielded_event=None,
        completed_response=None,
        final_text=final_text,
    )


def _handle_output_item_done(
    payload: dict[str, object],
    function_calls: dict[str, dict[str, object]],
    final_text: str | None,
    coerce_optional_dict: DictCoercer,
    handle_output_item_function_call: OutputItemFunctionCallHandler | None,
) -> StreamEventResult:
    item = coerce_optional_dict(payload.get("item"))
    yielded_event: dict[str, object] | None = None
    if item is not None:
        _collect_stream_function_call(function_calls, item)
        if item.get("type") == "function_call" and handle_output_item_function_call is not None:
            yielded_event = handle_output_item_function_call(item)

    return _build_result(
        handled=True,
        yielded_event=yielded_event,
        completed_response=None,
        final_text=final_text,
    )


def _handle_function_call_arguments_delta(
    payload: dict[str, object],
    function_calls: dict[str, dict[str, object]],
    final_text: str | None,
) -> StreamEventResult:
    _append_function_call_arguments(function_calls, payload)
    return _build_result(
        handled=True,
        yielded_event=None,
        completed_response=None,
        final_text=final_text,
    )


def _handle_function_call_arguments_done(
    payload: dict[str, object],
    function_calls: dict[str, dict[str, object]],
    final_text: str | None,
) -> StreamEventResult:
    _append_function_call_arguments(function_calls, payload)
    return _build_result(
        handled=True,
        yielded_event=None,
        completed_response=None,
        final_text=final_text,
    )


def _collect_stream_function_call(
    function_calls: dict[str, dict[str, object]], item: dict[str, object]
) -> None:
    if item.get("type") != "function_call":
        return

    call_id = _read_string(item.get("call_id"))
    if call_id is None:
        return

    entry = function_calls.setdefault(
        call_id,
        {
            "type": "function_call",
            "call_id": call_id,
            "name": _read_string(item.get("name")) or "",
            "arguments": "",
        },
    )

    name = _read_string(item.get("name"))
    if name:
        entry["name"] = name

    arguments = item.get("arguments")
    if isinstance(arguments, str):
        entry["arguments"] = arguments


def _append_function_call_arguments(
    function_calls: dict[str, dict[str, object]], event: dict[str, object]
) -> dict[str, object] | None:
    call_id = _read_string(event.get("call_id")) or _read_string(event.get("item_id"))
    if call_id is None:
        return None

    entry = function_calls.setdefault(
        call_id,
        {
            "type": "function_call",
            "call_id": call_id,
            "name": _read_string(event.get("name")) or "",
            "arguments": "",
        },
    )

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
        "call_id": call_id,
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


def _build_result(
    *,
    handled: bool,
    yielded_event: dict[str, object] | None,
    completed_response: dict[str, object] | None,
    final_text: str | None,
) -> StreamEventResult:
    return {
        "handled": handled,
        "yielded_event": yielded_event,
        "completed_response": completed_response,
        "final_text": final_text,
    }


def _read_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
