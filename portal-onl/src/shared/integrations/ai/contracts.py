from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class Function(BaseModel):
    """모델이 호출할 수 있는 function tool 계약을 표현합니다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    parameters: dict[str, Any]
    strict: bool = True
    type: Literal["function"] = "function"
    defer_loading: bool | None = None
    description: str | None = None
