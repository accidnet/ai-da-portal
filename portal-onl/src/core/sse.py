from pydantic import BaseModel


class SseEvent(BaseModel):
    """SSE 인코딩에 사용할 이벤트 타입과 payload를 표현합니다."""

    event_type: str | None = None
    data: dict[str, object]
