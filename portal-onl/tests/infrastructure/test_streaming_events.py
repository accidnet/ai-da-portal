from infrastructure.llm.streaming_events import RESPONSE_STREAMING_EVENTS


def test_response_streaming_event_groups() -> None:
    assert RESPONSE_STREAMING_EVENTS.response.created == "response.created"
    assert RESPONSE_STREAMING_EVENTS.response.completed == "response.completed"
    assert (
        RESPONSE_STREAMING_EVENTS.response.output_item.added
        == "response.output_item.added"
    )
    assert (
        RESPONSE_STREAMING_EVENTS.response.content_part.done
        == "response.content_part.done"
    )
    assert (
        RESPONSE_STREAMING_EVENTS.response.output_text.delta
        == "response.output_text.delta"
    )
    assert (
        RESPONSE_STREAMING_EVENTS.response.function_call_arguments.done
        == "response.function_call_arguments.done"
    )
    assert RESPONSE_STREAMING_EVENTS.message.delta == "message.delta"
    assert RESPONSE_STREAMING_EVENTS.message.completed == "message.completed"


def test_response_streaming_event_groups_ignore_unrelated_types() -> None:
    assert (
        RESPONSE_STREAMING_EVENTS.response.output_text.delta
        != RESPONSE_STREAMING_EVENTS.response.completed
    )
    assert (
        RESPONSE_STREAMING_EVENTS.response.output_text.done
        != RESPONSE_STREAMING_EVENTS.response.created
    )
    assert (
        RESPONSE_STREAMING_EVENTS.response.output_item.added
        != RESPONSE_STREAMING_EVENTS.message.delta
    )
    assert (
        RESPONSE_STREAMING_EVENTS.response.function_call_arguments.delta
        != RESPONSE_STREAMING_EVENTS.response.output_text.delta
    )
