import json
import logging
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from starlette.datastructures import UploadFile as StarletteUploadFile

from api.deps import get_agent_runtime, get_message_service
from domain.messages.schemas import ChatRequest, ChatResponse
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
    "/messages/stream",
    status_code=status.HTTP_202_ACCEPTED,
)
async def stream_message(
    request: Request,
    service: MessageService = Depends(get_message_service),
    agent_runtime: object = Depends(get_agent_runtime),
) -> StreamingResponse:
    try:
        payload, uploaded_file = await _parse_stream_request(request)
        payload, interaction_dataset = await service.prepare_chat_request(
            session_id=payload.session_id,
            message=payload.message,
            dataset_ids=payload.dataset_ids,
            file=uploaded_file,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    def event_stream() -> Generator[str, None, None]:
        try:
            logger.debug(
                "Streaming chat request received session_id=%s message_len=%s dataset_count=%s has_file=%s",
                payload.session_id,
                len(payload.message),
                len(payload.dataset_ids),
                interaction_dataset is not None,
            )

            if interaction_dataset is not None:
                yield _encode_sse_event(
                    {
                        "type": "dataset.ready",
                        "dataset": interaction_dataset.model_dump(mode="json"),
                    }
                )

            for event in service.stream_chat(payload=payload, agent_runtime=agent_runtime):
                yield _encode_sse_event(event)
        except LlmClientError as exc:
            logger.exception(
                "Streaming chat request failed session_id=%s dataset_count=%s",
                payload.session_id,
                len(payload.dataset_ids),
            )
            yield _encode_sse_event({"type": "error", "detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        status_code=status.HTTP_202_ACCEPTED,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


async def _parse_stream_request(request: Request) -> tuple[ChatRequest, UploadFile | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        file = form.get("file")
        if file is not None and not isinstance(file, StarletteUploadFile):
            raise ValueError("file must be a valid uploaded file.")

        session_id = form.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id is required.")

        message = form.get("message", "")
        if message is None:
            message = ""
        if not isinstance(message, str):
            raise ValueError("message must be a string.")

        dataset_ids_json = form.get("dataset_ids_json")
        if dataset_ids_json is not None and not isinstance(dataset_ids_json, str):
            raise ValueError("dataset_ids_json must be a string.")

        try:
            return (
                ChatRequest(
                    session_id=session_id,
                    message=message,
                    dataset_ids=_parse_dataset_ids(dataset_ids_json),
                ),
                file,
            )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    try:
        payload = ChatRequest.model_validate(await request.json())
    except json.JSONDecodeError as exc:
        raise ValueError("Request body must be valid JSON.") from exc
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    return payload, None


def _encode_sse_event(event: dict[str, object]) -> str:
    event_type = event.get("type")
    encoded = json.dumps(event, ensure_ascii=False)
    if isinstance(event_type, str) and event_type:
        return f"event: {event_type}\ndata: {encoded}\n\n"
    return f"data: {encoded}\n\n"
