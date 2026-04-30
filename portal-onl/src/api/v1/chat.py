from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from api.deps import (
    get_chat_streaming_agent_runtime,
    get_message_stream_service,
)
from agents.runtimes import ChatStreamingAgent
from domain.messages.stream_service import MessageStreamService

router = APIRouter()


@router.post("/messages", status_code=status.HTTP_202_ACCEPTED)
def send_message() -> None:
    pass


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
