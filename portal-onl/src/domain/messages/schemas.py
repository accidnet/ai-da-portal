from pydantic import BaseModel, Field


class MessageStreamRequest(BaseModel):
    """SSE 채팅 요청에 필요한 사용자 입력과 데이터셋 식별자입니다."""

    session_id: str
    message: str = ""
    uploaded_dataset_ids: list[str] = Field(default_factory=list)
