import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

MODELS_DEV_API_PATH = Path(__file__).with_name("models_dev_api.json")
DEFAULT_INPUT_TOKEN_LIMIT = 128_000
TOKEN_ESTIMATE_CHARS_PER_TOKEN = 4
PROTECTED_FUNCTION_NAMES = {"update_plan"}


type InputItemGroup = tuple[dict[str, object], ...]


def get_model_input_token_limit(*, provider: str, model: str) -> int:
    """models.dev catalog에서 provider/model의 input token 한도를 조회합니다."""
    catalog = _load_models_dev_catalog()
    provider_payload = _read_provider_payload(catalog, provider)
    model_payload = _read_model_payload(provider_payload, model)
    if model_payload is None:
        model_payload = _find_model_payload(catalog, model)

    limit = _read_limit(model_payload)
    return limit or DEFAULT_INPUT_TOKEN_LIMIT


def estimate_input_tokens(value: object) -> int:
    """Responses input payload의 token 수를 보수적으로 추정합니다."""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return max(1, math.ceil(len(text) / TOKEN_ESTIMATE_CHARS_PER_TOKEN))


def trim_input_items_to_token_limit(
    input_items: list[dict[str, object]],
    *,
    max_input_tokens: int,
    reserved_tokens: int = 0,
) -> list[dict[str, object]]:
    """모델 input 한도에 맞춰 오래된 재사용 input group부터 제외합니다."""
    if not input_items:
        return []

    budget = max(max_input_tokens - reserved_tokens, 1)
    groups = _group_input_items(input_items)
    selected_groups: list[InputItemGroup] = []
    selected_group_ids: set[int] = set()
    total_tokens = 0

    # update_plan은 진행 상태 복원에 필요하고, 최신 group은 현재 요청 맥락이므로 보호합니다.
    for index, group in enumerate(groups):
        if not _is_protected_group(group) and index != len(groups) - 1:
            continue
        selected_groups.append(group)
        selected_group_ids.add(index)
        total_tokens += estimate_input_tokens(group)

    for index in range(len(groups) - 1, -1, -1):
        if index in selected_group_ids:
            continue
        group = groups[index]
        group_tokens = estimate_input_tokens(group)
        if selected_groups and total_tokens + group_tokens > budget:
            break
        selected_groups.append(group)
        selected_group_ids.add(index)
        total_tokens += group_tokens
        if total_tokens >= budget:
            break

    return _flatten_groups_in_original_order(groups, selected_group_ids)


def _group_input_items(input_items: list[dict[str, object]]) -> list[InputItemGroup]:
    """function_call과 대응 function_call_output을 같은 trim 단위로 묶습니다."""
    call_index_by_id: dict[str, int] = {}
    grouped_indices: set[int] = set()
    groups_by_index: dict[int, list[dict[str, object]]] = {}

    for index, item in enumerate(input_items):
        if item.get("type") == "function_call":
            call_id = _read_call_id(item)
            if call_id is not None:
                call_index_by_id[call_id] = index
            groups_by_index.setdefault(index, []).append(item)
            grouped_indices.add(index)

    for index, item in enumerate(input_items):
        if item.get("type") != "function_call_output":
            continue
        call_id = _read_call_id(item)
        call_index = call_index_by_id.get(call_id or "")
        if call_index is not None:
            groups_by_index.setdefault(call_index, []).append(item)
        grouped_indices.add(index)

    groups: list[InputItemGroup] = []
    for index, item in enumerate(input_items):
        if index in groups_by_index:
            groups.append(tuple(groups_by_index[index]))
            continue
        if index not in grouped_indices:
            groups.append((item,))
    return groups


def _flatten_groups_in_original_order(
    groups: list[InputItemGroup],
    selected_group_ids: set[int],
) -> list[dict[str, object]]:
    """선택된 group을 원래 순서대로 펼칩니다."""
    items: list[dict[str, object]] = []
    for index, group in enumerate(groups):
        if index not in selected_group_ids:
            continue
        items.extend(group)
    return items


def _is_protected_group(group: InputItemGroup) -> bool:
    """항상 보존할 function call group인지 확인합니다."""
    return any(
        item.get("type") == "function_call"
        and isinstance(item.get("name"), str)
        and item["name"] in PROTECTED_FUNCTION_NAMES
        for item in group
    )


def _read_call_id(item: dict[str, object]) -> str | None:
    """Responses function call item에서 call_id를 읽습니다."""
    call_id = item.get("call_id")
    return call_id if isinstance(call_id, str) and call_id else None


@lru_cache
def _load_models_dev_catalog() -> dict[str, Any]:
    """다운로드된 models.dev api.json 파일을 로드합니다."""
    with MODELS_DEV_API_PATH.open(encoding="utf-8") as file:
        payload = json.load(file)
    return payload if isinstance(payload, dict) else {}


def _read_provider_payload(
    catalog: dict[str, Any],
    provider: str,
) -> dict[str, Any] | None:
    """provider id에 해당하는 catalog payload를 읽습니다."""
    normalized_provider = provider.strip().lower()
    payload = catalog.get(normalized_provider)
    return payload if isinstance(payload, dict) else None


def _read_model_payload(
    provider_payload: dict[str, Any] | None,
    model: str,
) -> dict[str, Any] | None:
    """provider payload에서 model payload를 읽습니다."""
    if provider_payload is None:
        return None
    models = provider_payload.get("models")
    if not isinstance(models, dict):
        return None
    model_payload = models.get(model)
    return model_payload if isinstance(model_payload, dict) else None


def _find_model_payload(catalog: dict[str, Any], model: str) -> dict[str, Any] | None:
    """provider 설정이 맞지 않아도 전체 catalog에서 model id를 보조 조회합니다."""
    for provider_payload in catalog.values():
        if not isinstance(provider_payload, dict):
            continue
        model_payload = _read_model_payload(provider_payload, model)
        if model_payload is not None:
            return model_payload
    return None


def _read_limit(model_payload: dict[str, Any] | None) -> int | None:
    """model payload에서 input token 한도를 읽습니다."""
    if model_payload is None:
        return None
    limit = model_payload.get("limit")
    if not isinstance(limit, dict):
        return None

    input_limit = _read_positive_int(limit.get("input"))
    if input_limit is not None:
        return input_limit

    context_limit = _read_positive_int(limit.get("context"))
    output_limit = _read_positive_int(limit.get("output")) or 0
    if context_limit is not None:
        return max(context_limit - output_limit, 1)
    return None


def _read_positive_int(value: object) -> int | None:
    """양수 정수 형태의 limit 값을 읽습니다."""
    if isinstance(value, int) and value > 0:
        return value
    return None
