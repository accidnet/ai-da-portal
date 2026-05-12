from pydantic import BaseModel, Field


class MessageStreamRequest(BaseModel):
    """SSE 채팅 요청에 필요한 사용자 입력과 데이터셋 식별자입니다."""

    session_id: str
    workspace_id: str | None = None
    message: str = ""
    # 현재 메시지가 참조하고 에이전트 컨텍스트로 사용할 데이터셋 목록입니다.
    dataset_ids: list[str] = Field(default_factory=list)
