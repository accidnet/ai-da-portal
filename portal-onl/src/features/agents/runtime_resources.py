import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from core.paths import DATA_DIR, ROOT_DIR

_BYTES_PER_MB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RuntimeResourceSnapshot:
    """agent 호출 시점의 컴퓨팅 리소스 상태를 표현합니다."""

    total_memory_mb: int | None
    available_memory_mb: int | None
    process_memory_mb: int | None
    root_disk_total_mb: int
    root_disk_free_mb: int
    data_disk_total_mb: int
    data_disk_free_mb: int
    cpu_count: int | None
    load_average_1m: float | None


def collect_runtime_resource_payload() -> dict[str, object]:
    """LLM developer message에 넣을 리소스 상태를 생성합니다."""
    snapshot = collect_runtime_resource_snapshot()
    return {
        "runtime_resources": asdict(snapshot),
    }


def collect_runtime_resource_snapshot() -> RuntimeResourceSnapshot:
    """현재 프로세스와 데이터 디렉터리 기준의 리소스 스냅샷을 수집합니다."""
    memory = _read_memory_info()
    root_disk = shutil.disk_usage(ROOT_DIR)
    data_disk_path = _existing_parent(DATA_DIR)
    data_disk = shutil.disk_usage(data_disk_path)
    return RuntimeResourceSnapshot(
        total_memory_mb=_bytes_to_mb(memory.get("MemTotal")),
        available_memory_mb=_bytes_to_mb(memory.get("MemAvailable")),
        process_memory_mb=_read_process_memory_mb(),
        root_disk_total_mb=_bytes_to_mb(root_disk.total) or 0,
        root_disk_free_mb=_bytes_to_mb(root_disk.free) or 0,
        data_disk_total_mb=_bytes_to_mb(data_disk.total) or 0,
        data_disk_free_mb=_bytes_to_mb(data_disk.free) or 0,
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


def _read_process_memory_mb() -> int | None:
    """현재 백엔드 프로세스의 RSS 메모리를 MB 단위로 읽습니다."""
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
    return _bytes_to_mb(resident_pages * os.sysconf("SC_PAGE_SIZE"))


def _read_load_average_1m() -> float | None:
    """OS가 제공하는 1분 load average를 읽습니다."""
    if not hasattr(os, "getloadavg"):
        return None
    try:
        return round(os.getloadavg()[0], 2)
    except OSError:
        return None


def _existing_parent(path: Path) -> Path:
    """아직 생성되지 않은 경로는 가장 가까운 상위 존재 경로로 대체합니다."""
    current = path
    while not current.exists() and current.parent != current:
        current = current.parent
    return current


def _bytes_to_mb(value: int | None) -> int | None:
    """byte 값을 MB 정수로 변환합니다."""
    if value is None:
        return None
    return int(value / _BYTES_PER_MB)
