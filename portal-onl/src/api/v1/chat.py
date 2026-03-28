from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_agent_runtime, get_message_service
from domain.messages.schemas import ChatRequest, ChatResponse
from domain.messages.service import MessageService
from infrastructure.llm.client import LlmClientError

router = APIRouter()


@router.post(
    "/messages", response_model=ChatResponse, status_code=status.HTTP_202_ACCEPTED
)
def send_message(
    payload: ChatRequest,
    service: MessageService = Depends(get_message_service),
    agent_runtime: object = Depends(get_agent_runtime),
) -> ChatResponse:
    try:
        return service.handle_chat(payload=payload, agent_runtime=agent_runtime)
    except LlmClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
