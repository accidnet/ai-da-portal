import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from core.config import get_settings
from core.paths import ROOT_DIR
from infrastructure.ai.model_catalog import (
    get_model_context_window_tokens,
    get_model_input_token_limit,
)

_BYTES_PER_GB = 1024 * 1024 * 1024
_MEMORY_SAFETY_MARGIN_GB = 1.0


@dataclass(frozen=True, slots=True)
class RuntimeResourceSnapshot:
    """agent 호출 시점의 컴퓨팅 리소스 상태를 표현합니다."""

    total_memory_gb: float | None
    available_memory_gb: float | None
    process_memory_gb: float | None
    root_disk_total_gb: float
    root_disk_free_gb: float
    cpu_count: int | None
    load_average_1m: float | None


def collect_runtime_resource_payload() -> dict[str, object]:
    """LLM developer message에 넣을 리소스 상태를 생성합니다."""
    snapshot = collect_runtime_resource_snapshot()
    settings = get_settings()
    return {
        "runtime_resources": asdict(snapshot),
        "llm_model": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            # 모델이 사용할 수 있는 전체 창과 실제 input trim 기준을 함께 제공합니다.
            "context_window_tokens": get_model_context_window_tokens(
                provider=settings.llm_provider,
                model=settings.llm_model,
            ),
            "max_input_tokens": get_model_input_token_limit(
                provider=settings.llm_provider,
                model=settings.llm_model,
            ),
        },
    }


def collect_runtime_resource_snapshot() -> RuntimeResourceSnapshot:
    """현재 프로세스와 루트 디스크 기준의 리소스 스냅샷을 수집합니다."""
    memory = _read_memory_info()
    root_disk = shutil.disk_usage(ROOT_DIR)
    available_memory_gb = _bytes_to_gb(memory.get("MemAvailable"))
    return RuntimeResourceSnapshot(
        total_memory_gb=_bytes_to_gb(memory.get("MemTotal")),
        available_memory_gb=_apply_memory_safety_margin(available_memory_gb),
        process_memory_gb=_read_process_memory_gb(),
        root_disk_total_gb=_bytes_to_gb(root_disk.total) or 0,
        root_disk_free_gb=_bytes_to_gb(root_disk.free) or 0,
        cpu_count=os.cpu_count(),
        load_average_1m=_read_load_average_1m(),
    )


def _read_memory_info() -> dict[str, int]:
    """Linux /proc/meminfo에서 메모리 정보를 byte 단위로 읽습니다."""
    meminfo_path = Path("/proc/meminfo")
    if not meminfo_path.is_file():
        return {}

    memory: dict[str, int] = {}
    for line in meminfo_path.read_text(encoding="utf-8").splitlines():
        name, _, raw_value = line.partition(":")
        parts = raw_value.strip().split()
        if not parts:
            continue
        try:
            value_kb = int(parts[0])
        except ValueError:
            continue
        memory[name] = value_kb * 1024
    return memory


def _apply_memory_safety_margin(available_memory_gb: float | None) -> float | None:
    """모델에 전달할 가용 메모리에서 작업 여유분을 차감합니다."""
    if available_memory_gb is None:
        return None

    # 실제 OS/백엔드 사용량 변동을 고려해 모델에는 보수적인 가용치를 전달합니다.
    return max(round(available_memory_gb - _MEMORY_SAFETY_MARGIN_GB, 2), 0)


def _read_process_memory_gb() -> float | None:
    """현재 백엔드 프로세스의 RSS 메모리를 GB 단위로 읽습니다."""
    statm_path = Path("/proc/self/statm")
    if not statm_path.is_file():
        return None

    parts = statm_path.read_text(encoding="utf-8").split()
    if len(parts) < 2:
        return None
    try:
        resident_pages = int(parts[1])
    except ValueError:
        return None
    return _bytes_to_gb(resident_pages * os.sysconf("SC_PAGE_SIZE"))


def _read_load_average_1m() -> float | None:
    """OS가 제공하는 1분 load average를 읽습니다."""
    if not hasattr(os, "getloadavg"):
        return None
    try:
        return round(os.getloadavg()[0], 2)
    except OSError:
        return None


def _bytes_to_gb(value: int | None) -> float | None:
    """byte 값을 GB 소수값으로 변환합니다."""
    if value is None:
        return None
    return round(value / _BYTES_PER_GB, 2)
