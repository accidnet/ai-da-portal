from dataclasses import dataclass, field
from typing import Literal, TypeAlias


InputMessageRole: TypeAlias = Literal["developer", "user", "assistant", "system"]
InputMessagePhase: TypeAlias = Literal["input", "output"]


@dataclass(frozen=True, slots=True)
class InputTextContent:
    text: str
    type: Literal["input_text"] = "input_text"

    def to_payload(self) -> dict[str, object]:
        return {
            "type": self.type,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class EasyInputMessage:
    role: InputMessageRole
    content: tuple[InputTextContent, ...]
    type: Literal["message"] = "message"
    phase: InputMessagePhase = "input"

    @classmethod
    def from_text(
        cls,
        *,
        role: InputMessageRole,
        text: str,
        phase: InputMessagePhase = "input",
    ) -> "EasyInputMessage":
        return cls(
            role=role,
            phase=phase,
            content=(InputTextContent(text=text),),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "type": self.type,
            "role": self.role,
            "phase": self.phase,
            "content": [part.to_payload() for part in self.content],
        }


@dataclass(frozen=True, slots=True)
class FunctionCallOutput:
    call_id: str
    output: str
    type: Literal["function_call_output"] = "function_call_output"
    status: Literal["completed"] = "completed"
    id: str | None = None

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": self.type,
            "call_id": self.call_id,
            "output": self.output,
            "status": self.status,
        }
        if self.id:
            payload["id"] = self.id
        return payload


InputItemPayload: TypeAlias = dict[str, object]
InputItem: TypeAlias = EasyInputMessage | FunctionCallOutput | InputItemPayload


@dataclass(frozen=True, slots=True)
class InputItemList:
    items: tuple[InputItem, ...] = field(default_factory=tuple)

    def to_payload(self) -> list[dict[str, object]]:
        payloads: list[dict[str, object]] = []
        for item in self.items:
            if isinstance(item, EasyInputMessage | FunctionCallOutput):
                payloads.append(item.to_payload())
            else:
                payloads.append(item)
        return payloads
