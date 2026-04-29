from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseOutputItemEventTypes:
    added: str = "response.output_item.added"
    done: str = "response.output_item.done"


@dataclass(frozen=True, slots=True)
class ResponseContentPartEventTypes:
    added: str = "response.content_part.added"
    done: str = "response.content_part.done"


@dataclass(frozen=True, slots=True)
class ResponseOutputTextEventTypes:
    delta: str = "response.output_text.delta"
    done: str = "response.output_text.done"


@dataclass(frozen=True, slots=True)
class ResponseFunctionCallArgumentEventTypes:
    delta: str = "response.function_call_arguments.delta"
    done: str = "response.function_call_arguments.done"


@dataclass(frozen=True, slots=True)
class MessageEventTypes:
    delta: str = "message.delta"
    completed: str = "message.completed"


@dataclass(frozen=True, slots=True)
class ResponseEventTypes:
    created: str = "response.created"
    in_progress: str = "response.in_progress"
    completed: str = "response.completed"
    failed: str = "response.failed"
    incomplete: str = "response.incomplete"
    output_item: ResponseOutputItemEventTypes = ResponseOutputItemEventTypes()
    content_part: ResponseContentPartEventTypes = ResponseContentPartEventTypes()
    output_text: ResponseOutputTextEventTypes = ResponseOutputTextEventTypes()
    function_call_arguments: ResponseFunctionCallArgumentEventTypes = (
        ResponseFunctionCallArgumentEventTypes()
    )


@dataclass(frozen=True, slots=True)
class ResponseStreamingEventTypes:
    response: ResponseEventTypes = ResponseEventTypes()
    message: MessageEventTypes = MessageEventTypes()


RESPONSE_STREAMING_EVENTS = ResponseStreamingEventTypes()
