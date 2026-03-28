import logging
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from api.deps import get_agent_runtime, get_message_service
from domain.messages.schemas import ChatInteractionResponse, ChatRequest, ChatResponse
from domain.messages.service import MessageService
from infrastructure.llm.client import LlmClientError

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/messages", response_model=ChatResponse, status_code=status.HTTP_202_ACCEPTED
)
def send_message(
    payload: ChatRequest,
    service: MessageService = Depends(get_message_service),
    agent_runtime: object = Depends(get_agent_runtime),
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
    "/interactions",
    response_model=ChatInteractionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_interaction(
    session_id: str = Form(...),
    message: str = Form(""),
    dataset_ids_json: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    service: MessageService = Depends(get_message_service),
    agent_runtime: object = Depends(get_agent_runtime),
) -> ChatInteractionResponse:
    try:
        dataset_ids = _parse_dataset_ids(dataset_ids_json)
        logger.debug(
            "Interaction request received session_id=%s message_len=%s dataset_count=%s has_file=%s",
            session_id,
            len(message),
            len(dataset_ids),
            file is not None,
        )
        return await service.handle_chat_interaction(
            session_id=session_id,
            message=message,
            dataset_ids=dataset_ids,
            file=file,
            agent_runtime=agent_runtime,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _parse_dataset_ids(dataset_ids_json: str | None) -> list[str]:
    if dataset_ids_json is None or not dataset_ids_json.strip():
        return []

    try:
        payload = json.loads(dataset_ids_json)
    except json.JSONDecodeError as exc:
        raise ValueError("dataset_ids_json must be a valid JSON array.") from exc

    if not isinstance(payload, list) or not all(
        isinstance(item, str) for item in payload
    ):
        raise ValueError("dataset_ids_json must be a JSON array of strings.")

    return payload
