from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResponseLifecycleEventTypes:
    created: str = "response.created"
    in_progress: str = "response.in_progress"
    completed: str = "response.completed"
    failed: str = "response.failed"
    incomplete: str = "response.incomplete"


@dataclass(frozen=True, slots=True)
class ResponseOutputItemEventTypes:
    added: str = "response.output_item.added"
    done: str = "response.output_item.done"

    def matches(self, event_type: object) -> bool:
        return event_type in {self.added, self.done}


@dataclass(frozen=True, slots=True)
class ResponseContentPartEventTypes:
    added: str = "response.content_part.added"
    done: str = "response.content_part.done"

    def matches(self, event_type: object) -> bool:
        return event_type in {self.added, self.done}


@dataclass(frozen=True, slots=True)
class ResponseOutputTextEventTypes:
    delta: str = "response.output_text.delta"
    done: str = "response.output_text.done"

    def is_delta(self, event_type: object) -> bool:
        return event_type == self.delta

    def is_done(self, event_type: object) -> bool:
        return event_type == self.done


@dataclass(frozen=True, slots=True)
class ResponseFunctionCallArgumentEventTypes:
    delta: str = "response.function_call_arguments.delta"
    done: str = "response.function_call_arguments.done"

    def matches(self, event_type: object) -> bool:
        return event_type in {self.delta, self.done}


@dataclass(frozen=True, slots=True)
class MessageStreamingEventTypes:
    message_delta: str = "message.delta"
    message_completed: str = "message.completed"

    def is_delta(self, event_type: object) -> bool:
        return event_type == self.message_delta

    def is_completed(self, event_type: object) -> bool:
        return event_type == self.message_completed


@dataclass(frozen=True, slots=True)
class ResponseStreamingEventTypes:
    response: ResponseLifecycleEventTypes = ResponseLifecycleEventTypes()
    output_item: ResponseOutputItemEventTypes = ResponseOutputItemEventTypes()
    content_part: ResponseContentPartEventTypes = ResponseContentPartEventTypes()
    output_text: ResponseOutputTextEventTypes = ResponseOutputTextEventTypes()
    function_call_arguments: ResponseFunctionCallArgumentEventTypes = (
        ResponseFunctionCallArgumentEventTypes()
    )
    message: MessageStreamingEventTypes = MessageStreamingEventTypes()

    def is_text_delta(self, event_type: object) -> bool:
        return event_type in {
            self.output_text.delta,
            self.message.message_delta,
        }

    def is_text_done(self, event_type: object) -> bool:
        return event_type in {
            self.output_text.done,
            self.message.message_completed,
        }

    def is_output_item(self, event_type: object) -> bool:
        return self.output_item.matches(event_type)

    def is_function_call_arguments(self, event_type: object) -> bool:
        return self.function_call_arguments.matches(event_type)


RESPONSE_STREAMING_EVENTS = ResponseStreamingEventTypes()
