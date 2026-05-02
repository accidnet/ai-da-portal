from typing import Literal, TypeAlias, Any

from pydantic import BaseModel, ConfigDict


EasyInputMessageRole: TypeAlias = Literal["developer", "user", "assistant", "system"]
EasyInputMessagePhase: TypeAlias = Literal["commentary", "final_answer"]


class _AiPayloadModel(BaseModel):
    """AI API payload 생성을 위한 불변 Pydantic 모델 기반 클래스입니다."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ResponseInputText(_AiPayloadModel):
    """Responses API 입력 텍스트 content 항목입니다."""

    text: str
    type: Literal["input_text"] = "input_text"

    def to_payload(self) -> dict[str, object]:
        """JSON 직렬화 가능한 입력 텍스트 payload로 변환합니다."""

        return {
            "type": self.type,
            "text": self.text,
        }


class EasyInputMessage(_AiPayloadModel):
    """문자열 또는 typed content를 받는 간단한 message 입력 항목입니다."""

    content: str | tuple[ResponseInputText, ...]
    role: EasyInputMessageRole
    type: Literal["message"] = "message"
    phase: EasyInputMessagePhase | None = None

    def to_payload(self) -> dict[str, object]:
        """Responses API message payload로 변환합니다."""

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


class Message(_AiPayloadModel):
    """Responses API 입력 message 항목입니다."""

    content: tuple[ResponseInputText, ...]
    role: MessageRole
    status: MessageStatus | None = None
    type: Literal["message"] = "message"

    def to_payload(self) -> dict[str, object]:
        """JSON 직렬화 가능한 message payload로 변환합니다."""

        payload: dict[str, object] = {
            "content": [part.to_payload() for part in self.content],
            "role": self.role,
            "type": self.type,
        }
        if self.status is not None:
            payload["status"] = self.status
        return payload


ResponseOutputMessagePhase: TypeAlias = Literal["commentary", "final_answer"]


class ResponseOutputText(_AiPayloadModel):
    """Responses API 출력 텍스트 content 항목입니다."""

    text: str
    annotations: Any = None
    logprobs: Any = None
    type: Literal["output_text"] = "output_text"

    def to_payload(self) -> dict[str, object]:
        """JSON 직렬화 가능한 출력 텍스트 payload로 변환합니다."""

        return {
            "text": self.text,
            "annotations": self.annotations,
            "logprobs": self.logprobs,
            "type": self.type,
        }


class ResponseOutputMessage(_AiPayloadModel):
    """Responses API 출력 message 항목입니다."""

    id: str
    content: tuple[ResponseOutputText, ...]
    role: Literal["assistant"] = "assistant"
    status: MessageStatus | None = None
    type: Literal["message"] = "message"
    phase: ResponseOutputMessagePhase | None = None

    def to_payload(self) -> dict[str, object]:
        """JSON 직렬화 가능한 출력 message payload로 변환합니다."""

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


class FunctionCall(_AiPayloadModel):
    """Responses API function_call 항목입니다."""

    arguments: str
    call_id: str
    name: str
    type: Literal["function_call"] = "function_call"
    id: str | None = None
    namespace: str | None = None
    status: MessageStatus | None = None

    def to_payload(self) -> dict[str, object]:
        """JSON 직렬화 가능한 function_call payload로 변환합니다."""

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


class FunctionCallOutput(_AiPayloadModel):
    """Responses API function_call_output 항목입니다."""

    call_id: str
    output: FunctionCallOutputContent
    type: Literal["function_call_output"] = "function_call_output"
    id: str | None = None
    status: MessageStatus | None = None

    def to_payload(self) -> dict[str, object]:
        """JSON 직렬화 가능한 function_call_output payload로 변환합니다."""

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
    EasyInputMessage | Message | FunctionCall | FunctionCallOutput | InputItemPayload
)


class InputItemList(_AiPayloadModel):
    """Responses API input 배열을 구성하는 입력 항목 목록입니다."""

    items: tuple[InputItem, ...] = ()

    def to_payload(self) -> list[dict[str, object]]:
        """Responses API 입력 항목을 JSON 직렬화 가능한 payload로 변환합니다."""

        payloads: list[dict[str, object]] = []
        for item in self.items:
            # 내부 Pydantic 입력 모델은 SDK 요청 전에 dict로 변환합니다.
            if isinstance(
                item, EasyInputMessage | Message | FunctionCall | FunctionCallOutput
            ):
                payloads.append(item.to_payload())
            else:
                payloads.append(item)
        return payloads
