from fastapi import APIRouter, Depends, status

from portal_onl.api.deps import get_agent_runtime, get_message_service
from portal_onl.domain.messages.schemas import ChatRequest, ChatResponse
from portal_onl.domain.messages.service import MessageService

router = APIRouter()


@router.post(
    "/messages", response_model=ChatResponse, status_code=status.HTTP_202_ACCEPTED
)
def send_message(
    payload: ChatRequest,
    service: MessageService = Depends(get_message_service),
    agent_runtime: object = Depends(get_agent_runtime),
) -> ChatResponse:
    return service.handle_chat(payload=payload, agent_runtime=agent_runtime)
