from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict


EasyInputMessageRole: TypeAlias = Literal["developer", "user", "assistant", "system"]
EasyInputMessagePhase: TypeAlias = Literal["commentary", "final_answer"]


class _AiPayloadModel(BaseModel):
    """AI API payload 생성을 위한 불변 Pydantic 모델 기반 클래스입니다."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Function(BaseModel):
    """모델이 호출할 수 있는 function tool 계약을 표현합니다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    parameters: dict[str, Any]
    strict: bool = True
    type: Literal["function"] = "function"
    defer_loading: bool | None = None
    description: str | None = None


class ResponseInputText(_AiPayloadModel):
    """Responses API 입력 텍스트 content 항목입니다."""

    text: str
    type: Literal["input_text"] = "input_text"


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
            [ResponseInputText(text=self.content).model_dump(mode="json")]
            if isinstance(self.content, str)
            else [part.model_dump(mode="json") for part in self.content]
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


ResponseOutputMessagePhase: TypeAlias = Literal["commentary", "final_answer"]


class ResponseOutputText(_AiPayloadModel):
    """Responses API 출력 텍스트 content 항목입니다."""

    text: str
    annotations: Any = None
    logprobs: Any = None
    type: Literal["output_text"] = "output_text"


class ResponseOutputMessage(_AiPayloadModel):
    """Responses API 출력 message 항목입니다."""

    content: tuple[ResponseOutputText, ...]
    id: str | None = None
    role: Literal["assistant"] = "assistant"
    status: MessageStatus | None = None
    type: Literal["message"] = "message"
    phase: ResponseOutputMessagePhase | None = None


class FunctionCall(_AiPayloadModel):
    """Responses API function_call 항목입니다."""

    arguments: str
    call_id: str
    name: str
    type: Literal["function_call"] = "function_call"
    id: str | None = None
    namespace: str | None = None
    status: MessageStatus | None = None


FunctionCallOutputContent: TypeAlias = str | tuple[ResponseInputText, ...]


class FunctionCallOutput(_AiPayloadModel):
    """Responses API function_call_output 항목입니다."""

    call_id: str
    output: FunctionCallOutputContent
    type: Literal["function_call_output"] = "function_call_output"
    id: str | None = None
    status: MessageStatus | None = None


InputItemPayload: TypeAlias = dict[str, object]
InputItem: TypeAlias = (
    EasyInputMessage
    | Message
    | ResponseOutputMessage
    | FunctionCall
    | FunctionCallOutput
    | InputItemPayload
)


class InputItemList(_AiPayloadModel):
    """Responses API input 배열을 구성하는 입력 항목 목록입니다."""

    items: tuple[InputItem, ...] = ()

    def to_payload(self) -> list[dict[str, object]]:
        """Responses API 입력 항목을 JSON 직렬화 가능한 payload로 변환합니다."""

        payloads: list[dict[str, object]] = []
        for item in self.items:
            # 내부 Pydantic 입력 모델은 SDK 요청 전에 dict로 변환합니다.
            if isinstance(item, EasyInputMessage):
                payloads.append(item.to_payload())
            elif isinstance(item, _AiPayloadModel):
                payloads.append(item.model_dump(mode="json", exclude_none=True))
            else:
                payloads.append(item)
        return payloads
