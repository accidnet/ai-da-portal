import json
import logging
from collections.abc import Generator, Iterable
from typing import cast

import httpx
from openai import APIConnectionError, APITimeoutError

from core.config import get_settings
from core.sse import SseEvent
from features.agents.llm_input_debug import (
    LlmInputDebugContext,
    write_llm_input_debug_file,
)
from features.agents.runtimes.base import BaseAgent
from features.agents.state import AgentInvokeInput, AgentInvokeOutput, PlanStep
from features.agents.stream_event_handlers import handle_stream_event
from features.tools.charts.dto import ChartPayload
from features.datasets.application.service import DatasetApplicationService
from infrastructure.ai.client import (
    AiClient,
    AiClientError,
    AiClientTransientError,
    coerce_optional_dict,
)
from infrastructure.ai.model_catalog import estimate_input_tokens
from shared.integrations.ai.contracts import (
    FunctionCall,
    InputItemList,
    ResponseOutputMessage,
)

logger = logging.getLogger(__name__)
INPUT_DEBUG_LARGEST_ITEM_COUNT = 8
INPUT_DEBUG_PREVIEW_CHARS = 240
STREAM_RECOVERY_TEXT_CHARS = 4000
STREAM_RECOVERY_EVENT_LIMIT = 30
AgentStreamEvent = dict[str, object] | SseEvent
CHART_FUNCTION_NAMES = {
    "build_trend_chart",
    "build_category_bar",
    "build_category_area",
    "build_correlation_scatter",
    "build_segment_bubble_chart",
    "build_distribution_histogram",
    "build_share_donut",
}


class ChatStreamingAgent(BaseAgent):
    """채팅 요청을 LLM 스트림과 tool 호출 이벤트로 실행하는 agent입니다."""

    def invoke(
        self, invoke_input: AgentInvokeInput
    ) -> Generator[AgentStreamEvent, None, AgentInvokeOutput]:
        workspace_id = invoke_input.get("workspace_id")
        workspace_local_path = invoke_input.get("workspace_local_path")
        workspace_dataset_files = invoke_input.get("workspace_dataset_files", [])
        self._configure_workspace_local_storage(
            workspace_id=workspace_id,
            workspace_local_path=workspace_local_path,
            workspace_dataset_files=workspace_dataset_files,
        )
        output = self._build_initial_output()
        output_input_items: list[dict[str, object]] = []

        # 사용자 메세지를 포함하여 AI API input으로 사용하기 위한 빌드
        input_items = self._build_initial_inputs(
            message=self._require_string(invoke_input, "message"),
            workspace_id=workspace_id,
            dataset_ids=invoke_input.get("dataset_ids", []),
            input_items=invoke_input.get("input_items", []),
        )

        # TODO: 개발중에만 일시적으로 정해두고, 이후에는 사용자 설정에서 가능하도록 할 예정.
        max_iterations = 20
        iteration_count = 0
        stream_recovery_count = 0
        plan_completion_requested = False
        while True:
            if iteration_count >= max_iterations:
                break
            iteration_count += 1

            # iteration이 시작할때마다 프론트에 전달
            yield SseEvent(
                event_type="agent.iteration.start",
                data={
                    "iteration": iteration_count,
                },
            )

            # 외부 LLM API 호출 중 발생한 provider 예외는 SSE error로 전환할 수 있게 정규화합니다.
            request_input_items: list[dict[str, object]] = []
            try:
                # StreamingResponse가 sync generator를 재개할 때 ContextVar가 보존되지 않을 수 있습니다.
                self._configure_workspace_local_storage(
                    workspace_id=workspace_id,
                    workspace_local_path=workspace_local_path,
                    workspace_dataset_files=workspace_dataset_files,
                )
                request_kwargs = self._build_llm_request_kwargs(input_items)
                request_input_items = self._read_request_input_items(request_kwargs)
                self._write_input_items_debug(
                    invoke_input=invoke_input,
                    iteration=iteration_count,
                    input_items=request_input_items,
                )
                stream_result = yield from self._parse_stream_events(
                    self._llm_client.create_response(
                        **request_kwargs,
                        stream=True,
                    ),
                )
            except AiClientTransientError as exc:
                stream_result = self._build_interrupted_stream_result(
                    exc=exc,
                    partial_text="",
                    event_log=[],
                    completed_output_items=[],
                )
            except AiClientError as exc:
                if self._is_context_window_error(exc):
                    self._write_context_window_error_debug(
                        invoke_input=invoke_input,
                        iteration=iteration_count,
                        input_items=request_input_items,
                        exc=exc,
                    )
                raise
            except Exception as exc:
                if self._is_context_window_error(exc):
                    self._write_context_window_error_debug(
                        invoke_input=invoke_input,
                        iteration=iteration_count,
                        input_items=request_input_items,
                        exc=exc,
                    )
                raise AiClientError(self._format_llm_stream_error(exc)) from exc
            if stream_result.get("interrupted") is True:
                stream_recovery_count += 1
                yield SseEvent(
                    event_type="agent.iteration.interrupted",
                    data={
                        "iteration": iteration_count,
                        "attempt": stream_recovery_count,
                        "max_attempts": self._max_stream_recovery_attempts(),
                    },
                )
                yield SseEvent(
                    event_type="agent.iteration.done",
                    data={
                        "iteration": iteration_count,
                    },
                )
                if stream_recovery_count > self._max_stream_recovery_attempts():
                    raise AiClientError(
                        "LLM streaming request was interrupted repeatedly. "
                        "Please retry the message."
                    )
                input_items.append(
                    self._build_stream_interruption_recovery_input(
                        iteration=iteration_count,
                        stream_result=stream_result,
                    )
                )
                continue

            stream_recovery_count = 0
            function_call_items = cast(
                list[FunctionCall],
                stream_result.get("function_call_items", []),
            )
            should_stop_iteration = stream_result.get("should_stop_iteration") is True

            # API 호출이 끝난 후 처리하는 로직
            # tool 실행 직전에도 요청 단위 workspace context를 복구합니다.
            self._configure_workspace_local_storage(
                workspace_id=workspace_id,
                workspace_local_path=workspace_local_path,
                workspace_dataset_files=workspace_dataset_files,
            )
            new_input_items, function_events = self._handle_after_call_completion(
                stream_result=stream_result,
                output=output,
            )
            stream_input_items = self._build_stream_input_item_payloads(stream_result)
            # 만약, API 호출이 끝난 후 처리 로직 중 프론트로 전달해야 하는 것이 있을 경우
            for event in function_events:
                yield event

            # iteration이 끝날때마다 프론트에 전달
            yield SseEvent(
                event_type="agent.iteration.done",
                data={
                    "iteration": iteration_count,
                },
            )

            # iteration이 끝날때 새로운 input_items을 추가하여 iteration내에 멀티턴을 위함
            if new_input_items:
                input_items.extend(new_input_items)
                output_input_items.extend(new_input_items)
            elif stream_input_items:
                # function call이 없는 최종 assistant message도 저장할 input으로 남깁니다.
                output_input_items.extend(stream_input_items)

            # 실행할 function call이 없고 답변 message가 완료되면 iteration을 종료합니다.
            if not function_call_items and should_stop_iteration:
                # 진행 중인 plan이 남아 있으면 종료 직전 한 번 더 상태 갱신을 유도합니다.
                if self._should_request_plan_completion(
                    output=output,
                    already_requested=plan_completion_requested,
                ):
                    if stream_input_items:
                        input_items.extend(stream_input_items)
                    input_items.append(self._build_plan_completion_input(output))
                    plan_completion_requested = True
                    continue

                break

        output["input_items"] = output_input_items
        return output

    def _build_input_debug_context(
        self,
        *,
        invoke_input: AgentInvokeInput,
        iteration: int,
        event: str,
    ) -> LlmInputDebugContext:
        """chat streaming 디버그 파일을 요청/턴/반복 단위로 식별합니다."""
        return {
            "event": event,
            "session_id": invoke_input.get("session_id"),
            "user_message_id": invoke_input.get("user_message_id"),
            "agent_run_id": invoke_input.get("agent_run_id"),
            "iteration": iteration,
        }

    def _write_input_items_debug(
        self,
        *,
        invoke_input: AgentInvokeInput,
        iteration: int,
        input_items: list[dict[str, object]],
    ) -> None:
        """chat streaming LLM 호출 직전 input item payload를 JSON으로 저장합니다."""
        context = self._build_input_debug_context(
            invoke_input=invoke_input,
            iteration=iteration,
            event="input-items",
        )
        debug_file_path = write_llm_input_debug_file(
            context=context,
            payload={
                "input_item_count": len(input_items),
                "input_items": input_items,
            },
        )
        if debug_file_path is not None:
            logger.info(
                "Saved chat streaming input item debug file=%s", debug_file_path
            )

    def _write_context_window_error_debug(
        self,
        *,
        invoke_input: AgentInvokeInput,
        iteration: int,
        input_items: list[dict[str, object]],
        exc: Exception,
    ) -> None:
        """context window 초과 시 원인 추적용 input item 원본과 크기 요약을 저장합니다."""
        context = self._build_input_debug_context(
            invoke_input=invoke_input,
            iteration=iteration,
            event="context-window-error",
        )
        debug_file_path = write_llm_input_debug_file(
            context=context,
            payload={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "input_summary": self._summarize_input_items(
                    input_items,
                    truncate_preview=False,
                ),
                "input_items": input_items,
            },
        )
        if debug_file_path is not None:
            logger.warning(
                "Saved context window input debug file=%s",
                debug_file_path,
            )

    def _read_request_input_items(
        self, request_kwargs: dict[str, object]
    ) -> list[dict[str, object]]:
        """LLM request kwargs에서 실제 호출에 사용될 input item 목록만 추출합니다."""
        input_items = request_kwargs.get("input")
        if not isinstance(input_items, list):
            return []
        return [item for item in input_items if isinstance(item, dict)]

    def _summarize_input_items(
        self,
        input_items: list[dict[str, object]],
        *,
        truncate_preview: bool = True,
    ) -> dict[str, object]:
        """context 초과 원인을 찾기 위한 item별 크기와 입력 종류를 요약합니다."""
        summaries = [
            self._summarize_input_item(
                index=index,
                item=item,
                truncate_preview=truncate_preview,
            )
            for index, item in enumerate(input_items)
        ]
        total_tokens = sum(
            summary["estimated_tokens"]
            for summary in summaries
            if isinstance(summary.get("estimated_tokens"), int)
        )
        total_chars = sum(
            summary["estimated_chars"]
            for summary in summaries
            if isinstance(summary.get("estimated_chars"), int)
        )
        return {
            "count": len(input_items),
            "estimated_tokens": total_tokens,
            "estimated_chars": total_chars,
            "items": summaries,
            "largest_items": sorted(
                summaries,
                key=lambda summary: int(summary.get("estimated_tokens") or 0),
                reverse=True,
            )[:INPUT_DEBUG_LARGEST_ITEM_COUNT],
        }

    def _summarize_input_item(
        self,
        *,
        index: int,
        item: dict[str, object],
        truncate_preview: bool,
    ) -> dict[str, object]:
        """단일 input item의 식별 정보와 대략적인 크기를 기록합니다."""
        preview = self._extract_input_item_preview(item)
        return {
            "index": index,
            "type": item.get("type"),
            "role": item.get("role"),
            "name": item.get("name"),
            "call_id": item.get("call_id"),
            "status": item.get("status"),
            "phase": item.get("phase"),
            "estimated_tokens": estimate_input_tokens(item),
            "estimated_chars": len(json.dumps(item, ensure_ascii=False, default=str)),
            "preview": self._truncate_preview(preview) if truncate_preview else preview,
        }

    def _extract_input_item_preview(self, value: object) -> str:
        """중첩 input item에서 어떤 입력인지 판단할 짧은 문자열을 추출합니다."""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("text", "output", "arguments", "content"):
                child = value.get(key)
                if isinstance(child, str):
                    return child
                if isinstance(child, list):
                    preview = self._extract_input_item_preview(child)
                    if preview:
                        return preview
            return ""
        if isinstance(value, list):
            previews = [self._extract_input_item_preview(child) for child in value[:3]]
            return " | ".join(preview for preview in previews if preview)
        return ""

    def _truncate_preview(self, value: str) -> str:
        """큰 입력 원인을 식별할 수 있을 정도로만 preview를 제한합니다."""
        normalized = " ".join(value.split())
        if len(normalized) <= INPUT_DEBUG_PREVIEW_CHARS:
            return normalized
        return f"{normalized[:INPUT_DEBUG_PREVIEW_CHARS]}..."

    def _build_initial_output(self) -> AgentInvokeOutput:
        """invoke 입력과 분리된 agent 출력 기본값을 생성합니다."""
        return {
            "input_items": [],
            "assistant_message": "",
            "used_tools": [],
            "plan": [],
            "plan_explanation": None,
            "resolved_dataset_id": None,
            "analysis_type": None,
        }

    def _parse_stream_events(
        self, stream: object
    ) -> Generator[AgentStreamEvent, None, dict[str, object]]:
        """API 호출 1번 내에 발생하는 stream event에 대한 개별적 처리"""

        # streaming 중에 생성되는 input을 순차적으로 적재하여, 다음 step input에 추가하여 활용하기 위함
        input_items: list[ResponseOutputMessage | FunctionCall] = []
        function_call_items: list[FunctionCall] = []
        partial_text_parts: list[str] = []
        event_log: list[dict[str, object]] = []
        should_stop_iteration = False

        close = getattr(stream, "close", None)
        try:
            try:
                for event in cast(Iterable[object], stream):
                    # TODO: 해당 부분은 AI Client 부분에서 처리되어서 넘어올수있게끔 가능한 지 확인 후 수정
                    payload = coerce_optional_dict(event)

                    if payload is None:
                        self._log_unhandled_stream_event(event)
                        continue

                    self._append_stream_event_log(event_log, payload)
                    partial_delta = self._extract_stream_delta(payload)
                    if partial_delta:
                        partial_text_parts.append(partial_delta)

                    # streaming의 각 type별로 처리
                    processed_event = handle_stream_event(payload=payload)

                    # 바로 프론트로 전달해야하는 경우
                    yielded_event = processed_event.yielded_event
                    if isinstance(yielded_event, SseEvent):
                        yield yielded_event

                    # input에 넣을 item이 있을 경우 추가
                    input_item = processed_event.input_item
                    if input_item:
                        input_items.append(input_item)

                    # 실행해야할 function call이 있을 경우 추가
                    function_call_item = processed_event.function_call_item
                    if function_call_item:
                        function_call_items.append(function_call_item)

                    # message output item 완료 여부를 iteration 종료 조건에 활용합니다.
                    if processed_event.should_stop_iteration:
                        should_stop_iteration = True
            except Exception as exc:
                if not self._is_recoverable_stream_error(exc):
                    raise
                logger.warning(
                    "LLM stream interrupted; continuing with recovery input error_type=%s error=%s",
                    type(exc).__name__,
                    exc,
                )
                return self._build_interrupted_stream_result(
                    exc=exc,
                    partial_text="".join(partial_text_parts),
                    event_log=event_log,
                    completed_output_items=self._build_stream_input_item_payloads(
                        {"input_items": input_items}
                    ),
                )

        finally:
            if callable(close):
                close()

        return {
            "input_items": input_items,
            "function_call_items": function_call_items,
            "should_stop_iteration": should_stop_iteration,
        }

    def _build_interrupted_stream_result(
        self,
        *,
        exc: Exception,
        partial_text: str,
        event_log: list[dict[str, object]],
        completed_output_items: list[dict[str, object]],
    ) -> dict[str, object]:
        """중단된 LLM 호출을 다음 iteration에서 복구할 수 있는 결과로 정규화합니다."""
        return {
            "input_items": [],
            "function_call_items": [],
            "should_stop_iteration": False,
            "interrupted": True,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "partial_text": self._truncate_recovery_text(partial_text),
            "event_log": event_log,
            "completed_output_items": completed_output_items,
        }

    def _build_stream_interruption_recovery_input(
        self,
        *,
        iteration: int,
        stream_result: dict[str, object],
    ) -> dict[str, object]:
        """중단된 LLM 스트림의 진행 로그를 다음 iteration용 developer input으로 만듭니다."""
        payload = {
            "iteration": iteration,
            "error_type": stream_result.get("error_type"),
            "error_message": stream_result.get("error_message"),
            "partial_text_sent_to_user": stream_result.get("partial_text") or "",
            "recent_stream_events": stream_result.get("event_log") or [],
            "completed_output_items": stream_result.get("completed_output_items") or [],
        }
        text = (
            "이전 LLM 스트림이 네트워크 또는 타임아웃 문제로 중단되었습니다. "
            "사용자 요청은 실패한 것이 아니며, 다음 로그를 바탕으로 같은 요청 처리를 이어가세요. "
            "이미 사용자에게 스트리밍된 텍스트는 반복하지 말고, 필요한 tool 호출이나 최종 답변 생성을 계속하세요.\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}"
        )
        return {
            "type": "message",
            "role": "developer",
            "content": [
                {
                    "type": "input_text",
                    "text": text,
                }
            ],
        }

    def _append_stream_event_log(
        self,
        event_log: list[dict[str, object]],
        payload: dict[str, object],
    ) -> None:
        """복구 입력에 쓸 최근 스트림 이벤트 요약을 제한된 크기로 유지합니다."""
        event_log.append(self._summarize_stream_event(payload))
        if len(event_log) > STREAM_RECOVERY_EVENT_LIMIT:
            del event_log[: len(event_log) - STREAM_RECOVERY_EVENT_LIMIT]

    def _summarize_stream_event(self, payload: dict[str, object]) -> dict[str, object]:
        """중단 지점 재현에 필요한 스트림 이벤트 핵심 필드만 남깁니다."""
        summary: dict[str, object] = {"type": payload.get("type")}
        for key in ("item_id", "output_index", "content_index", "sequence_number"):
            value = payload.get(key)
            if value is not None:
                summary[key] = value

        delta = self._extract_stream_delta(payload)
        if delta:
            summary["delta_preview"] = self._truncate_preview(delta)

        item = coerce_optional_dict(payload.get("item"))
        if item is not None:
            summary["item"] = self._summarize_stream_item(item)
        return summary

    def _summarize_stream_item(self, item: dict[str, object]) -> dict[str, object]:
        """완료된 output item을 복구 판단에 충분한 수준으로 요약합니다."""
        summary: dict[str, object] = {
            "type": item.get("type"),
            "role": item.get("role"),
            "status": item.get("status"),
            "phase": item.get("phase"),
            "name": item.get("name"),
            "call_id": item.get("call_id"),
        }
        arguments = item.get("arguments")
        if isinstance(arguments, str):
            summary["arguments_preview"] = self._truncate_preview(arguments)
        preview = self._extract_input_item_preview(item)
        if preview:
            summary["preview"] = self._truncate_preview(preview)
        return {key: value for key, value in summary.items() if value is not None}

    def _extract_stream_delta(self, payload: dict[str, object]) -> str | None:
        """텍스트 delta 이벤트에서 복구용 문자열 조각을 추출합니다."""
        delta = payload.get("delta")
        return delta if isinstance(delta, str) and delta else None

    def _truncate_recovery_text(self, value: str) -> str:
        """복구 입력이 과도하게 커지지 않도록 partial text를 제한합니다."""
        normalized = value.strip()
        if len(normalized) <= STREAM_RECOVERY_TEXT_CHARS:
            return normalized
        return normalized[-STREAM_RECOVERY_TEXT_CHARS:]

    def _max_stream_recovery_attempts(self) -> int:
        """설정값이 잘못되어도 최소 0 이상의 복구 횟수로 정규화합니다."""
        return max(0, int(get_settings().llm_stream_recovery_attempts))

    def _is_recoverable_stream_error(self, exc: Exception) -> bool:
        """스트림 중단 후 같은 요청을 이어가도 되는 일시적 네트워크 오류를 판별합니다."""
        if self._is_context_window_error(exc):
            return False
        if isinstance(
            exc,
            (
                APIConnectionError,
                APITimeoutError,
                TimeoutError,
                ConnectionError,
                httpx.NetworkError,
                httpx.TimeoutException,
            ),
        ):
            return True

        normalized_message = str(exc).lower()
        return any(
            marker in normalized_message
            for marker in (
                "timed out",
                "timeout",
                "connection reset",
                "connection aborted",
                "network",
                "server disconnected",
                "incomplete chunk",
                "peer closed",
            )
        )

    def _build_stream_input_item_payloads(
        self, stream_result: dict[str, object]
    ) -> list[dict[str, object]]:
        """스트림에서 생성된 response item을 다음 input 재사용 payload로 변환합니다."""
        stream_input_items = cast(
            list[ResponseOutputMessage | FunctionCall],
            stream_result.get("input_items", []),
        )
        if not stream_input_items:
            return []
        return InputItemList(items=tuple(stream_input_items)).to_payload()

    def _should_request_plan_completion(
        self,
        *,
        output: AgentInvokeOutput,
        already_requested: bool,
    ) -> bool:
        """최종 답변 직후 남은 plan 상태를 갱신할 추가 iteration이 필요한지 판단합니다."""
        if already_requested:
            return False

        plan = output.get("plan", [])
        if not plan:
            return False

        # pending 또는 in_progress가 남아 있으면 종료 전 update_plan을 한 번 더 허용합니다.
        return any(
            isinstance(step, dict) and step.get("status") != "completed"
            for step in plan
        )

    def _build_plan_completion_input(
        self,
        output: AgentInvokeOutput,
    ) -> dict[str, object]:
        """남은 plan 단계만 완료 상태로 정리하도록 LLM에 전달할 내부 입력을 만듭니다."""
        plan = [
            step
            for step in output.get("plan", [])
            if isinstance(step, dict) and isinstance(step.get("step"), str)
        ]
        return {
            "type": "message",
            "role": "developer",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        "최종 답변은 이미 작성했습니다. 새 최종 답변을 작성하지 말고, "
                        "현재 계획에 pending 또는 in_progress 단계가 남아 있으면 "
                        "update_plan tool로 실제 완료된 단계의 status를 completed로 갱신하세요. "
                        f"현재 계획: {json.dumps(plan, ensure_ascii=False)}"
                    ),
                }
            ],
        }

    def _log_unhandled_stream_event(self, event: object) -> None:
        if event is None or event == "" or event == [] or event == {}:
            return

        logger.warning(
            "Unhandled stream event payload type=%s value=%r",
            type(event).__name__,
            event,
        )

    def _format_llm_stream_error(self, exc: Exception) -> str:
        """LLM 스트리밍 예외를 사용자에게 전달 가능한 메시지로 정규화합니다."""
        if self._is_context_window_error(exc):
            return (
                "LLM 입력이 모델 context window를 초과했습니다. "
                "이전 대화 또는 tool 결과가 너무 커서 최근 대화만 다시 시도해 주세요."
            )
        return f"LLM streaming request failed: {str(exc)}"

    def _is_context_window_error(self, exc: Exception) -> bool:
        """provider별 context window 초과 메시지를 공통 조건으로 판별합니다."""
        message = str(exc)
        normalized_message = message.lower()
        return (
            "context window" in normalized_message
            or "input exceeds" in normalized_message
            or "context_length_exceeded" in normalized_message
            or "maximum context length" in normalized_message
            or "too many tokens" in normalized_message
        )

    def _handle_after_call_completion(
        self,
        *,
        stream_result: dict[str, object],
        output: AgentInvokeOutput,
    ) -> tuple[list[dict[str, object]] | None, list[SseEvent]]:

        stream_input_items = self._build_stream_input_item_payloads(stream_result)

        # 실행해야 할 function call이 있는 지 확인 후 실행
        function_call_items = cast(
            list[FunctionCall],
            stream_result.get("function_call_items", []),
        )
        function_call_outputs, function_events = self._handle_function_call_items(
            function_call_items=function_call_items,
        )
        self._apply_function_call_results_to_output(
            output=output,
            function_call_items=function_call_items,
            function_call_outputs=function_call_outputs,
        )
        if function_call_outputs:
            new_input_items = [
                *stream_input_items,
                *function_call_outputs.values(),
            ]

            return new_input_items, function_events

        return None, function_events

    def _apply_function_call_results_to_output(
        self,
        *,
        output: AgentInvokeOutput,
        function_call_items: list[FunctionCall],
        function_call_outputs: dict[str, dict[str, object]],
    ) -> None:
        """실행된 tool 결과 중 저장/응답에 필요한 값을 agent 출력에 반영합니다."""
        self._append_used_tools(output, function_call_items)
        for function_name, function_call_output in function_call_outputs.items():
            tool_result = self._decode_tool_output(function_call_output)
            if not isinstance(tool_result, dict) or tool_result.get("ok") is not True:
                continue
            data = tool_result.get("data")
            if isinstance(data, dict):
                self._apply_tool_data_to_output(
                    output=output,
                    function_name=function_name,
                    data=data,
                )

    def _apply_tool_data_to_output(
        self,
        *,
        output: AgentInvokeOutput,
        function_name: str,
        data: dict[str, object],
    ) -> None:
        """tool 성공 data를 agent 출력 필드로 정규화합니다."""
        if function_name == "update_plan":
            plan = data.get("plan")
            if isinstance(plan, list):
                output["plan"] = [
                    cast(PlanStep, item) for item in plan if isinstance(item, dict)
                ]
            explanation = data.get("explanation")
            output["plan_explanation"] = (
                explanation if isinstance(explanation, str) else None
            )
            return

        dataset_id = data.get("dataset_id")
        if isinstance(dataset_id, str):
            output["resolved_dataset_id"] = dataset_id

        analytics = data.get("analytics")
        if isinstance(analytics, dict):
            return

        chart = data.get("chart")
        if isinstance(chart, dict):
            ChartPayload.model_validate(chart)

    def _handle_function_call_items(
        self,
        *,
        function_call_items: list[FunctionCall],
    ) -> tuple[dict[str, dict[str, object]], list[SseEvent]]:
        """function_call을 실행하고 프론트 전달 이벤트를 생성합니다."""
        if not function_call_items:
            return {}, []

        function_call_outputs = self._execute_function_call_items(
            function_call_items=function_call_items,
        )
        events = self._build_function_call_events(
            function_call_outputs=function_call_outputs,
        )
        return function_call_outputs, events

    def _build_function_call_events(
        self,
        *,
        function_call_outputs: dict[str, dict[str, object]],
    ) -> list[SseEvent]:
        """function_call output을 SSE 이벤트 목록으로 변환합니다."""
        events = self._build_tool_output_events(function_call_outputs)
        update_plan_event = self._build_update_plan_event(
            function_call_outputs=function_call_outputs,
        )
        if update_plan_event is not None:
            events.append(update_plan_event)

        chart_event = self._build_chart_event(function_call_outputs)
        if chart_event is not None:
            events.append(chart_event)

        return events

    def _build_tool_output_events(
        self,
        function_call_outputs: dict[str, dict[str, object]],
    ) -> list[SseEvent]:
        """실행된 tool 결과를 히스토리/디버깅용 SSE 이벤트로 변환합니다."""
        events: list[SseEvent] = []
        for function_name, function_call_output in function_call_outputs.items():
            tool_result = self._decode_tool_output(function_call_output)
            if not isinstance(tool_result, dict):
                continue
            events.append(
                SseEvent(
                    event_type="agent.function_call.output",
                    data={
                        "name": function_name,
                        "ok": tool_result.get("ok") is True,
                        "text": self._summarize_tool_result(function_name, tool_result),
                    },
                )
            )
        return events

    def _summarize_tool_result(
        self, function_name: str, tool_result: dict[str, object]
    ) -> str:
        """tool result를 화면 히스토리에 저장할 짧은 문자열로 요약합니다."""
        if tool_result.get("ok") is not True:
            error = tool_result.get("error")
            return f"{function_name} failed: {error or 'Unknown error'}"

        data = tool_result.get("data")
        if isinstance(data, dict):
            chart = data.get("chart")
            if isinstance(chart, dict):
                title = chart.get("title")
                chart_type = chart.get("type")
                return f"{function_name} generated {title or 'a chart'} ({chart_type or 'chart'})."
            plan = data.get("plan")
            if isinstance(plan, list):
                return f"{function_name} updated {len(plan)} plan steps."
        return f"{function_name} completed."

    def _build_update_plan_event(
        self,
        *,
        function_call_outputs: dict[str, dict[str, object]],
    ) -> SseEvent | None:
        """update_plan 결과를 agent.iteration.plan 이벤트로 변환합니다."""
        update_plan_function_output = function_call_outputs.get("update_plan")
        if not update_plan_function_output:
            return None

        tool_result = self._decode_tool_output(update_plan_function_output)
        if not isinstance(tool_result, dict) or tool_result.get("ok") is not True:
            return None

        return SseEvent(
            event_type="agent.iteration.plan",
            data=tool_result,
        )

    def _build_chart_event(
        self,
        function_call_outputs: dict[str, dict[str, object]],
    ) -> SseEvent | None:
        """chart tool 결과를 agent.iteration.chart 이벤트로 변환합니다."""
        for function_name in CHART_FUNCTION_NAMES:
            function_call_output = function_call_outputs.get(function_name)
            tool_result = self._decode_tool_output(function_call_output)
            if not isinstance(tool_result, dict) or tool_result.get("ok") is not True:
                continue

            data = tool_result.get("data")
            if not isinstance(data, dict):
                continue
            chart = data.get("chart")
            if not isinstance(chart, dict):
                continue

            return SseEvent(
                event_type="agent.iteration.chart",
                data={
                    "dataset_id": data.get("dataset_id"),
                    "source_id": data.get("source_id"),
                    "chart": chart,
                },
            )

        return None

    def _decode_tool_output(
        self,
        function_call_output: dict[str, object] | None,
    ) -> dict[str, object] | None:
        """function_call_output의 JSON output을 dict로 복원합니다."""
        if not function_call_output:
            return None
        output = function_call_output.get("output")
        if not isinstance(output, str):
            return None
        try:
            decoded = json.loads(output)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def _append_used_tools(
        self,
        output: AgentInvokeOutput,
        function_call_items: list[FunctionCall],
    ) -> None:
        """실행된 function_call 이름을 최종 출력에 누적합니다."""
        if not function_call_items:
            return

        used_tools = [
            tool for tool in output.get("used_tools", []) if isinstance(tool, str)
        ]
        for function_call in function_call_items:
            used_tools.append(function_call.name)
        output["used_tools"] = used_tools


def build_chat_streaming_agent(
    *,
    llm_client: AiClient,
    dataset_service: DatasetApplicationService,
) -> ChatStreamingAgent:
    """스트리밍 채팅 agent 인스턴스를 생성합니다."""
    return ChatStreamingAgent(
        llm_client=llm_client,
        dataset_service=dataset_service,
    )
