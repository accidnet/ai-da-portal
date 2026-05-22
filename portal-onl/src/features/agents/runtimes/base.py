import gc
import json
import logging
from collections.abc import Mapping
from typing import cast

from core.config import get_settings
from features.agents.prompt_loader import load_prompt
from features.agents.runtime_resources import collect_runtime_resource_payload
from features.agents.state import (
    AgentInvokeOutput,
    AgentState,
    AgentStateSnapshot,
    PlanStep,
)
from features.datasets.application.service import DatasetApplicationService
from features.data_sources.domain.models import DataSourceItem
from features.data_sources.infrastructure.repositories import DataSourceRepository
from infrastructure.ai.client import AiClient, AiClientError
from infrastructure.ai.model_catalog import (
    estimate_input_tokens,
    get_model_input_token_limit,
    trim_input_items_to_token_limit,
)
from infrastructure.db.repositories.dataset_repository import (
    DatasetRecord,
    DatasetRepository,
    DatasetSourceRecord,
)
from shared.integrations.ai.contracts import (
    Message,
    FunctionCall,
    FunctionCallOutput,
    InputItemList,
    ResponseInputText,
)
from features.tools import registry
from features.tools.workspace_files.context import (
    set_workspace_file_context,
    workspace_usage_payload,
)

logger = logging.getLogger(__name__)
INPUT_DEBUG_EDGE_ITEM_COUNT = 10
INPUT_DEBUG_LARGEST_ITEM_COUNT = 8
INPUT_DEBUG_PREVIEW_CHARS = 240


class BaseAgent:
    """공통 LLM 호출과 tool 실행 상태 관리를 담당하는 agent 기반 클래스입니다."""

    def __init__(
        self,
        *,
        llm_client: AiClient,
        dataset_service: DatasetApplicationService,
    ) -> None:
        self._llm_client = llm_client
        self._dataset_service = dataset_service

    def snapshot_output(self, output: AgentInvokeOutput) -> AgentStateSnapshot:
        """agent 출력 값을 API와 저장소에서 쓰는 스냅샷으로 정규화합니다."""
        assistant_message = self._read_string(output.get("assistant_message")) or ""
        plan = [
            cast(PlanStep, step)
            for step in output.get("plan", [])
            if isinstance(step, dict)
        ]

        return {
            "assistant_message": assistant_message,
            "used_tools": [
                tool for tool in output.get("used_tools", []) if isinstance(tool, str)
            ],
            "plan": plan,
            "plan_explanation": (
                output.get("plan_explanation")
                if isinstance(output.get("plan_explanation"), str)
                else None
            ),
            "resolved_dataset_id": self._read_string(output.get("resolved_dataset_id")),
            "analysis_type": self._read_string(output.get("analysis_type")),
        }

    def snapshot_state(self, state: AgentState) -> AgentStateSnapshot:
        """이전 state 기반 호출부를 출력 스냅샷 정규화로 위임합니다."""
        return self.snapshot_output(cast(AgentInvokeOutput, state))

    def cleanup_runtime_resources(self) -> None:
        """단일 agent 스트리밍 호출이 끝난 뒤 요청 단위 메모리를 정리합니다."""
        registry.cleanup_runtime_memory()
        gc.collect()

    def _configure_workspace_local_storage(
        self,
        *,
        workspace_id: str | None,
        workspace_local_path: str | None,
    ) -> None:
        """agent tool 실행에서 사용할 워크스페이스 로컬 저장소 컨텍스트를 설정합니다."""
        set_workspace_file_context(
            workspace_id=workspace_id,
            local_path=workspace_local_path,
        )

    def _build_developer_input(self, *, dataset_ids: list[str]) -> Message:
        """업로드 데이터셋 정보를 모델 입력용 개발자 메시지로 활용합니다."""
        payload = self._build_dataset_context_payload(dataset_ids)
        return Message(
            role="developer",
            content=(
                ResponseInputText(
                    text=(
                        "다음의 데이터셋 및 원천 데이터 정보를 활용하세요.\n"
                        f"{json.dumps(payload, ensure_ascii=False)}"
                    )
                ),
            ),
        )

    def _build_dataset_context_payload(
        self,
        dataset_ids: list[str],
    ) -> dict[str, object]:
        """dataset_id 목록을 DB 기준 dataset/source 메타데이터로 확장합니다."""
        datasets: list[DatasetRecord] = []
        missing_dataset_ids: list[str] = []
        dataset_repository = DatasetRepository()

        for dataset_id in dict.fromkeys(dataset_ids):
            try:
                datasets.append(dataset_repository.get_or_raise(dataset_id))
            except KeyError:
                missing_dataset_ids.append(dataset_id)

        source_items = self._load_source_items_by_id(datasets)
        return {
            "datasets": [
                self._build_dataset_context(dataset, source_items)
                for dataset in datasets
            ],
            "missing_dataset_ids": missing_dataset_ids,
            "usage_note": ("데이터셋은 여러 원천 데이터 파일을 포함할 수 있습니다. "),
        }

    def _load_source_items_by_id(
        self,
        datasets: list[DatasetRecord],
    ) -> dict[str, DataSourceItem]:
        """dataset source_ref_id에 해당하는 원천 데이터 노드를 일괄 조회합니다."""
        source_ref_ids = [
            source.source_ref_id
            for dataset in datasets
            for source in dataset.sources
            if source.source_ref_id is not None
        ]
        unique_source_ref_ids = list(dict.fromkeys(source_ref_ids))
        if not unique_source_ref_ids:
            return {}

        source_items = DataSourceRepository().list_items_by_ids(unique_source_ref_ids)
        return {item.id: item for item in source_items}

    def _build_dataset_context(
        self,
        dataset: DatasetRecord,
        source_items: dict[str, DataSourceItem],
    ) -> dict[str, object]:
        """단일 dataset의 기본 정보와 원천 source 목록을 모델 입력용으로 변환합니다."""
        return {
            "dataset_id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
            "created_at": dataset.created_at.isoformat(),
            "updated_at": dataset.updated_at.isoformat(),
            "sources": [
                self._build_source_context(source, source_items)
                for source in dataset.sources
            ],
        }

    def _build_source_context(
        self,
        source: DatasetSourceRecord,
        source_items: dict[str, DataSourceItem],
    ) -> dict[str, object]:
        """dataset source row와 원천 데이터 노드 정보를 하나의 payload로 합칩니다."""
        source_item = (
            source_items.get(source.source_ref_id)
            if source.source_ref_id is not None
            else None
        )
        payload: dict[str, object] = {
            "dataset_source_id": source.id,
            "source_id": source.source_ref_id,
            "row_count": source.row_count,
            "column_count": source.column_count,
        }
        if source_item is None:
            payload["source_type"] = "direct_upload"
            return payload

        payload.update(
            {
                "source_type": source_item.item_type,
                "name": source_item.name,
                "relative_path": source_item.relative_path,
                "content_type": source_item.content_type,
                "size_bytes": source_item.size_bytes,
            }
        )
        return payload

    def _build_initial_inputs(
        self,
        *,
        message: str,
        dataset_ids: list[str],
        input_items: list[dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        """초기 LLM 요청 input 목록을 구성합니다."""
        inputs = []
        if dataset_ids:
            inputs.append(self._build_developer_input(dataset_ids=dataset_ids))

        if input_items:
            inputs.extend(input_items)
        else:
            inputs.append(Message(role="user", content=(ResponseInputText(text=message),)))

        return InputItemList(items=inputs).to_payload()

    def _execute_function_call_items(
        self, function_call_items: list[FunctionCall] | None
    ) -> dict[str, dict[str, object]]:
        """function_call 목록을 실행하고 다음 input용 output item을 이름별로 반환합니다."""
        if not function_call_items:
            return {}

        function_call_outputs: dict[str, dict[str, object]] = {}
        for function_call in function_call_items:
            tool_result = registry.execute_tool(
                function_call.name,
                function_call.arguments,
            )
            function_call_output_params = function_call.model_dump(
                mode="json",
                include={"call_id", "id", "status"},
                exclude_none=True,
            )
            function_call_outputs[function_call.name] = FunctionCallOutput(
                **function_call_output_params,
                output=json.dumps(tool_result, ensure_ascii=False),
            ).model_dump(mode="json", exclude_none=True)
        return function_call_outputs

    def _build_state_event(self, state: AgentState) -> dict[str, object]:
        """프론트로 전달할 agent.state 이벤트 payload를 구성합니다."""
        return {
            "type": "agent.state",
            "state": self._serialize_snapshot(self.snapshot_state(state)),
        }

    def _serialize_snapshot(self, snapshot: AgentStateSnapshot) -> dict[str, object]:
        return {
            "assistant_message": snapshot["assistant_message"],
            "used_tools": snapshot["used_tools"],
            "plan": snapshot["plan"],
            "plan_explanation": snapshot["plan_explanation"],
            "resolved_dataset_id": snapshot["resolved_dataset_id"],
            "analysis_type": snapshot["analysis_type"],
        }

    def _build_llm_request_kwargs(
        self, input_items: list[dict[str, object]]
    ) -> dict[str, object]:
        input_payload = self._build_model_limited_input(input_items)
        # 외부 LLM API 호출에 필요한 요청 파라미터를 구성합니다.
        return {
            "instructions": load_prompt("base.md"),
            "input": input_payload,
            "tools": registry.get_tool_definitions(),
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "reasoning": {"effort": "medium"},
        }

    def _build_model_limited_input(
        self, input_items: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """현재 모델의 input token 한도에 맞게 최종 LLM input payload를 구성합니다."""
        injected_input = self._inject_runtime_resource_input(input_items)
        settings = get_settings()
        max_input_tokens = get_model_input_token_limit(
            provider=settings.llm_provider,
            model=settings.llm_model,
        )
        reserved_tokens = self._estimate_non_input_request_tokens()
        trimmed_input = trim_input_items_to_token_limit(
            injected_input,
            max_input_tokens=max_input_tokens,
            reserved_tokens=reserved_tokens,
        )
        self._log_llm_input_debug(
            model=settings.llm_model,
            max_input_tokens=max_input_tokens,
            reserved_tokens=reserved_tokens,
            before_items=injected_input,
            after_items=trimmed_input,
        )
        if len(trimmed_input) != len(injected_input):
            logger.info(
                "Trimmed LLM input items by model token limit model=%s before=%s after=%s max_input_tokens=%s",
                settings.llm_model,
                len(injected_input),
                len(trimmed_input),
                max_input_tokens,
            )
        return trimmed_input

    def _estimate_non_input_request_tokens(self) -> int:
        """instructions와 tool definition이 차지하는 대략적인 input token을 예약합니다."""
        return estimate_input_tokens(load_prompt("base.md")) + estimate_input_tokens(
            registry.get_tool_definitions()
        )

    def _log_llm_input_debug(
        self,
        *,
        model: str,
        max_input_tokens: int,
        reserved_tokens: int,
        before_items: list[dict[str, object]],
        after_items: list[dict[str, object]],
    ) -> None:
        """LLM input 크기 원인을 추적할 수 있게 compact preview 로그를 남깁니다."""
        payload = {
            "model": model,
            "max_input_tokens": max_input_tokens,
            "reserved_tokens": reserved_tokens,
            "available_input_tokens": max(max_input_tokens - reserved_tokens, 1),
            "before": self._summarize_input_items(before_items),
            "after": self._summarize_input_items(after_items),
        }
        logger.info(
            "LLM input items debug preview=%s",
            json.dumps(payload, ensure_ascii=False),
        )

    def _summarize_input_items(
        self, input_items: list[dict[str, object]]
    ) -> dict[str, object]:
        """input item 목록을 로그용 크기/preview 정보로 요약합니다."""
        summaries = [
            self._summarize_input_item(index=index, item=item)
            for index, item in enumerate(input_items)
        ]
        total_tokens = sum(
            summary["estimated_tokens"]
            for summary in summaries
            if isinstance(summary.get("estimated_tokens"), int)
        )
        return {
            "count": len(input_items),
            "estimated_tokens": total_tokens,
            "items": self._select_edge_summaries(summaries),
            "largest_items": sorted(
                summaries,
                key=lambda summary: int(summary.get("estimated_tokens") or 0),
                reverse=True,
            )[:INPUT_DEBUG_LARGEST_ITEM_COUNT],
        }

    def _select_edge_summaries(
        self, summaries: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """긴 item 목록은 앞/뒤 일부만 보여줘 로그 크기를 제한합니다."""
        edge_count = INPUT_DEBUG_EDGE_ITEM_COUNT
        if len(summaries) <= edge_count * 2:
            return summaries
        return [
            *summaries[:edge_count],
            {
                "omitted_items": len(summaries) - edge_count * 2,
            },
            *summaries[-edge_count:],
        ]

    def _summarize_input_item(
        self,
        *,
        index: int,
        item: dict[str, object],
    ) -> dict[str, object]:
        """단일 Responses input item의 로그용 preview를 생성합니다."""
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
            "preview": self._truncate_preview(preview),
        }

    def _extract_input_item_preview(self, value: object) -> str:
        """중첩 payload에서 사람이 볼 만한 짧은 문자열 후보를 추출합니다."""
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
            previews = [
                self._extract_input_item_preview(child)
                for child in value[:3]
            ]
            return " | ".join(preview for preview in previews if preview)
        return ""

    def _truncate_preview(self, value: str) -> str:
        """로그 preview 문자열 길이를 제한합니다."""
        normalized = " ".join(value.split())
        if len(normalized) <= INPUT_DEBUG_PREVIEW_CHARS:
            return normalized
        return f"{normalized[:INPUT_DEBUG_PREVIEW_CHARS]}..."

    def _inject_runtime_resource_input(
        self, input_items: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """LLM API 호출 직전 최신 컴퓨팅 리소스 상태를 developer input으로 추가합니다."""
        developer_inputs = [self._build_runtime_resource_input()]
        workspace_input = self._build_workspace_local_storage_input()
        if workspace_input is not None:
            developer_inputs.append(workspace_input)
        logger.debug("Built runtime developer inputs=%s", developer_inputs)
        insert_index = 0
        for item in input_items:
            if item.get("role") != "developer":
                break
            insert_index += 1
        return [
            *input_items[:insert_index],
            *developer_inputs,
            *input_items[insert_index:],
        ]

    def _build_runtime_resource_input(self) -> dict[str, object]:
        """현재 리소스 스냅샷을 모델 입력용 developer message로 변환합니다."""
        payload = collect_runtime_resource_payload()
        return InputItemList(
            items=(
                Message(
                    role="developer",
                    content=(
                        ResponseInputText(
                            text=(
                                "현재 백엔드 컴퓨팅 리소스 상태입니다. "
                                "데이터 로드, 전처리, 집계, 임시 파일 생성 방식을 결정할 때 참고하세요.\n"
                                f"{json.dumps(payload, ensure_ascii=False)}"
                            )
                        ),
                    ),
                ),
            )
        ).to_payload()[0]

    def _build_workspace_local_storage_input(self) -> dict[str, object] | None:
        """워크스페이스 로컬 저장소 사용 안내를 모델 입력용 developer message로 변환합니다."""
        payload = workspace_usage_payload()
        if payload is None:
            return None

        return InputItemList(
            items=(
                Message(
                    role="developer",
                    content=(
                        ResponseInputText(
                            text=(
                                "현재 워크스페이스에서 사용할 수 있는 로컬 저장소 정보입니다.\n"
                                f"{json.dumps(payload, ensure_ascii=False)}"
                            )
                        ),
                    ),
                ),
            )
        ).to_payload()[0]

    def _read_string(self, value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _require_string(self, values: Mapping[str, object], key: str) -> str:
        value = values.get(key)
        if isinstance(value, str) and value:
            return value
        raise AiClientError(f"Agent state is missing required field: {key}")
