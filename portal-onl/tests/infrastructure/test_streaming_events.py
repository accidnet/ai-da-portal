from infrastructure.llm.streaming_events import RESPONSE_STREAMING_EVENTS


def test_response_streaming_event_groups() -> None:
    assert RESPONSE_STREAMING_EVENTS.response.completed == "response.completed"
    assert RESPONSE_STREAMING_EVENTS.output_item.added == "response.output_item.added"
    assert RESPONSE_STREAMING_EVENTS.content_part.done == "response.content_part.done"
    assert RESPONSE_STREAMING_EVENTS.output_text.delta == "response.output_text.delta"
    assert (
        RESPONSE_STREAMING_EVENTS.function_call_arguments.done
        == "response.function_call_arguments.done"
    )
    assert RESPONSE_STREAMING_EVENTS.is_text_delta("response.output_text.delta")
    assert RESPONSE_STREAMING_EVENTS.is_text_delta("message.delta")
    assert RESPONSE_STREAMING_EVENTS.is_text_done("response.output_text.done")
    assert RESPONSE_STREAMING_EVENTS.is_text_done("message.completed")
    assert RESPONSE_STREAMING_EVENTS.is_output_item("response.output_item.added")
    assert RESPONSE_STREAMING_EVENTS.is_output_item("response.output_item.done")
    assert RESPONSE_STREAMING_EVENTS.is_function_call_arguments(
        "response.function_call_arguments.delta"
    )
    assert RESPONSE_STREAMING_EVENTS.is_function_call_arguments(
        "response.function_call_arguments.done"
    )


def test_response_streaming_event_groups_ignore_unrelated_types() -> None:
    assert not RESPONSE_STREAMING_EVENTS.is_text_delta("response.completed")
    assert not RESPONSE_STREAMING_EVENTS.is_text_done("response.created")
    assert not RESPONSE_STREAMING_EVENTS.is_output_item("message.delta")
    assert not RESPONSE_STREAMING_EVENTS.is_function_call_arguments(
        "response.output_text.delta"
    )
