import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from api.deps import (
    get_chat_agent_runtime,
    get_chat_streaming_agent_runtime,
    get_message_service,
    get_message_stream_service,
)
from agents.runtimes import ChatAgent, ChatStreamingAgent
from domain.messages.schemas import ChatRequest, ChatResponse
from domain.messages.service import MessageService
from domain.messages.stream_service import MessageStreamService
from infrastructure.llm.client import LlmClientError

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/messages", response_model=ChatResponse, status_code=status.HTTP_202_ACCEPTED
)
def send_message(
    payload: ChatRequest,
    service: MessageService = Depends(get_message_service),
    agent_runtime: ChatAgent = Depends(get_chat_agent_runtime),
) -> ChatResponse:
    try:
        logger.debug(
            "Chat request received session_id=%s message_len=%s dataset_count=%s",
            payload.session_id,
            len(payload.message),
            len(payload.dataset_ids),
        )
        return service.handle_chat(payload=payload, agent_runtime=agent_runtime)
    except LlmClientError as exc:
        logger.exception(
            "Chat request failed session_id=%s dataset_count=%s",
            payload.session_id,
            len(payload.dataset_ids),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


@router.post(
    "/messages/stream",
    status_code=status.HTTP_202_ACCEPTED,
)
async def stream_message(
    request: Request,
    stream_service: MessageStreamService = Depends(get_message_stream_service),
    agent_runtime: ChatStreamingAgent = Depends(get_chat_streaming_agent_runtime),
) -> StreamingResponse:
    return await stream_service.create_streaming_response(
        request=request,
        agent_runtime=agent_runtime,
    )
