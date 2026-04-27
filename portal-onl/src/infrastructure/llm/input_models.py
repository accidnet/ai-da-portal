from dataclasses import dataclass, field
from typing import Literal, TypeAlias, Any


EasyInputMessageRole: TypeAlias = Literal["developer", "user", "assistant", "system"]
EasyInputMessagePhase: TypeAlias = Literal["commentary", "final_answer"]


@dataclass(frozen=True, slots=True)
class ResponseInputText:
    text: str
    type: Literal["input_text"] = "input_text"

    def to_payload(self) -> dict[str, object]:
        return {
            "type": self.type,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class EasyInputMessage:
    content: str | tuple[ResponseInputText, ...]
    role: EasyInputMessageRole
    type: Literal["message"] = "message"
    phase: EasyInputMessagePhase | None = None

    def to_payload(self) -> dict[str, object]:
        # 일반 문자열과 타입 지정 콘텐츠를 같은 Responses 형식으로 직렬화합니다.
        content = (
            [ResponseInputText(text=self.content).to_payload()]
            if isinstance(self.content, str)
            else [part.to_payload() for part in self.content]
        )
        payload: dict[str, object] = {
            "content": content,
            "role": self.role,
            "type": self.type,
        }
        # 선택 필드는 값이 있을 때만 포함합니다.
        if self.phase is not None:
            payload["phase"] = self.phase
        return payload


MessageRole: TypeAlias = Literal["developer", "user", "system"]
MessageStatus: TypeAlias = Literal["in_progress", "completed", "incomplete"]


@dataclass(frozen=True, slots=True)
class Message:
    content: tuple[ResponseInputText, ...]
    role: MessageRole
    status: MessageStatus | None = None
    type: Literal["message"] = "message"

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "content": [part.to_payload() for part in self.content],
            "role": self.role,
            "type": self.type,
        }
        if self.status is not None:
            payload["status"] = self.status
        return payload


ResponseOutputMessagePhase: TypeAlias = Literal["commentary", "final_answer"]


@dataclass(frozen=True, slots=True)
class ResponseOutputText:
    text: str
    annotations: Any = None
    logprobs: Any = None
    type: Literal["output_text"] = "output_text"

    def to_payload(self) -> dict[str, object]:
        return {
            "text": self.text,
            "annotations": self.annotations,
            "logprobs": self.logprobs,
            "type": self.type,
        }


@dataclass(frozen=True, slots=True)
class ResponseOutputMessage:
    id: str
    content: tuple[ResponseOutputText, ...]
    role: Literal["assistant"] = "assistant"
    status: MessageStatus | None = None
    type: Literal["message"] = "message"
    phase: ResponseOutputMessagePhase | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "content": [part.to_payload() for part in self.content],
            "role": self.role,
            "type": self.type,
        }
        if self.status is not None:
            payload["status"] = self.status
        if self.phase is not None:
            payload["phase"] = self.phase
        return payload


@dataclass(frozen=True, slots=True)
class FunctionCall:
    arguments: str
    call_id: str
    name: str
    type: Literal["function_call"] = "function_call"
    id: str | None = None
    namespace: str | None = None
    status: MessageStatus | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "arguments": self.arguments,
            "call_id": self.call_id,
            "name": self.name,
            "type": self.type,
        }
        # API 반환 시 채워지는 선택 필드는 값이 있을 때만 포함합니다.
        if self.id is not None:
            payload["id"] = self.id
        if self.namespace is not None:
            payload["namespace"] = self.namespace
        if self.status is not None:
            payload["status"] = self.status
        return payload


FunctionCallOutputContent: TypeAlias = str | tuple[ResponseInputText, ...]


@dataclass(frozen=True, slots=True)
class FunctionCallOutput:
    call_id: str
    output: FunctionCallOutputContent
    type: Literal["function_call_output"] = "function_call_output"
    id: str | None = None
    status: MessageStatus | None = None

    def to_payload(self) -> dict[str, object]:
        # 도구 결과는 문자열 또는 typed content 배열 형식 모두 지원합니다.
        output: object = (
            self.output
            if isinstance(self.output, str)
            else [part.to_payload() for part in self.output]
        )
        payload: dict[str, object] = {
            "type": self.type,
            "call_id": self.call_id,
            "output": output,
        }
        if self.id is not None:
            payload["id"] = self.id
        if self.status is not None:
            payload["status"] = self.status
        return payload


InputItemPayload: TypeAlias = dict[str, object]
InputItem: TypeAlias = (
    EasyInputMessage | FunctionCall | FunctionCallOutput | InputItemPayload
)


@dataclass(frozen=True, slots=True)
class InputItemList:
    items: tuple[InputItem, ...] = field(default_factory=tuple)

    def to_payload(self) -> list[dict[str, object]]:
        payloads: list[dict[str, object]] = []
        for item in self.items:
            if isinstance(item, EasyInputMessage | FunctionCall | FunctionCallOutput):
                payloads.append(item.to_payload())
            else:
                payloads.append(item)
        return payloads
