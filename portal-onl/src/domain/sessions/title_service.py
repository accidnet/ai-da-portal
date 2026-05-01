import logging
import re
from collections.abc import Iterable
from typing import cast

from domain.sessions.service import SessionService
from infrastructure.ai.client import AiClient, AiClientError
from infrastructure.ai.streaming_events import RESPONSE_STREAMING_EVENTS

logger = logging.getLogger(__name__)


class SessionTitleService:
    def __init__(self, llm_client: AiClient, session_service: SessionService) -> None:
        self._llm_client = llm_client
        self._session_service = session_service

    def resolve_title(self, *, session_id: str, user_message: str) -> str:
        # 기본 제목 상태의 세션에만 첫 메시지 기반 제목을 저장합니다.
        normalized_session_id = session_id.strip()
        if not normalized_session_id:
            raise ValueError("session_id is required.")

        session = self._session_service.ensure_session(normalized_session_id)
        if not self._session_service.is_auto_title_candidate(session.title):
            return session.title

        generated_title = self._generate_session_title(user_message)
        return self._session_service.update_title_if_default(
            session_id=normalized_session_id,
            title=generated_title,
        ).title

    def _generate_session_title(self, user_message: str) -> str:
        try:
            generated = self._llm_client.generate(
                system=(
                    "당신은 데이터 분석 대화의 세션 제목 생성기입니다. "
                    "사용자 첫 질문을 12~30자 안팎의 매우 짧은 한국어 제목 1개로만 요약하세요. "
                    "따옴표, 마침표, 번호, 설명 문장은 포함하지 마세요."
                ),
                user_message=f"첫 사용자 질문:\n{user_message}",
            )
            sanitized = self._sanitize_session_title(
                self._resolve_generated_text(generated)
            )
            if sanitized:
                return sanitized
        except AiClientError as exc:
            logger.info(
                "Session title generation failed; using fallback detail=%s", exc
            )

        return self._fallback_session_title(user_message)

    def _resolve_generated_text(self, generated: object) -> str:
        if isinstance(generated, str):
            return generated

        final_text: str | None = None
        deltas: list[str] = []
        close = getattr(generated, "close", None)

        try:
            for event in cast(Iterable[object], generated):
                payload = self._coerce_optional_dict(event)
                if payload is None:
                    continue

                event_type = payload.get("type")
                if (
                    event_type == RESPONSE_STREAMING_EVENTS.response.output_text.delta
                    or event_type == RESPONSE_STREAMING_EVENTS.message.delta
                ):
                    delta = payload.get("delta") or payload.get("text")
                    if isinstance(delta, str) and delta:
                        deltas.append(delta)
                    continue

                if (
                    event_type == RESPONSE_STREAMING_EVENTS.response.output_text.done
                    or event_type == RESPONSE_STREAMING_EVENTS.message.completed
                ):
                    text = payload.get("text") or payload.get("delta")
                    if isinstance(text, str) and text.strip():
                        final_text = text.strip()
                    continue

                if event_type == RESPONSE_STREAMING_EVENTS.response.completed:
                    response_payload = self._coerce_optional_dict(
                        payload.get("response")
                    )
                    if response_payload is None:
                        continue
                    completed = self._extract_output_text(response_payload)
                    if completed:
                        return completed
        finally:
            if callable(close):
                close()

        output = final_text or "".join(deltas).strip()
        if output:
            return output
        raise AiClientError("OpenAI returned no assistant text.")

    def _extract_output_text(self, payload: dict[str, object]) -> str | None:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = payload.get("output")
        if not isinstance(output, list):
            return None

        parts: list[str] = []
        for item in output:
            item_payload = self._coerce_optional_dict(item)
            if item_payload is None:
                continue
            content = item_payload.get("content")
            if not isinstance(content, list):
                continue
            for entry in content:
                entry_payload = self._coerce_optional_dict(entry)
                if entry_payload is None:
                    continue
                text = entry_payload.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return "\n\n".join(parts)
        return None

    def _coerce_optional_dict(self, value: object) -> dict[str, object] | None:
        if isinstance(value, dict):
            return cast(dict[str, object], value)

        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="python")
            if isinstance(dumped, dict):
                return cast(dict[str, object], dumped)

        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            dumped = to_dict()
            if isinstance(dumped, dict):
                return cast(dict[str, object], dumped)

        return None

    def _sanitize_session_title(self, title: str) -> str | None:
        sanitized = " ".join(title.strip().split())
        sanitized = sanitized.strip("'\"“”‘’`「」[](){}<>")
        sanitized = re.sub(r"^[\-•*#\d\s.:]+", "", sanitized)
        sanitized = re.sub(r"[.?!。！？]+$", "", sanitized)
        sanitized = re.split(r"[\r\n]", sanitized, maxsplit=1)[0].strip()
        if not sanitized:
            return None
        return sanitized[:30].rstrip()

    def _fallback_session_title(self, user_message: str) -> str:
        cleaned = re.sub(r"\s+", " ", user_message).strip()
        cleaned = cleaned.strip("'\"“”‘’`「」[](){}<>")
        cleaned = re.sub(r"[?!.。！？]+$", "", cleaned)
        first_chunk = re.split(r"[.?!。！？\n]+", cleaned, maxsplit=1)[0].strip()
        if len(first_chunk) >= 12:
            cleaned = first_chunk
        if not cleaned:
            return "새 분석 요청"
        if len(cleaned) <= 30:
            return cleaned
        return f"{cleaned[:29].rstrip()}…"
