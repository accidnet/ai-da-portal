from pydantic import BaseModel, Field


class MessageStreamRequest(BaseModel):
    """SSE 채팅 요청에 필요한 사용자 입력과 데이터셋 식별자입니다."""

    session_id: str
    workspace_id: str | None = None
    message: str = ""
    # 에이전트 컨텍스트로 사용할 세션 내 데이터셋 목록입니다.
    uploaded_dataset_ids: list[str] = Field(default_factory=list)
    # 현재 사용자 메시지에 실제 첨부된 데이터셋만 메시지별 링크로 저장합니다.
    attached_dataset_ids: list[str] = Field(default_factory=list)
