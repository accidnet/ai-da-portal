#!/usr/bin/env python3
"""개발용 원천 데이터 파일/폴더 직접 적재 스크립트입니다.

웹 업로드를 거치지 않고 로컬 파일을 `data_source_items` DB row와
`data/data_sources` flat storage 파일로 적재합니다.

사용 예:
    .venv/bin/python scripts/import_data_sources.py data/finance
    .venv/bin/python scripts/import_data_sources.py /path/to/file.csv --no-root-folder
"""

from __future__ import annotations

import argparse
import mimetypes
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from sqlalchemy import select


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.paths import DATA_SOURCE_STORAGE_DIR  # noqa: E402
from features.data_sources.infrastructure.orm import DataSourceItemOrm  # noqa: E402
from infrastructure.db.session import SessionLocal, init_database  # noqa: E402


SUPPORTED_SUFFIXES = {".csv", ".txt", ".tsv", ".xlsx", ".xls", ".json"}
COPY_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ImportFile:
    """적재할 로컬 파일과 DB에 저장할 상대 경로입니다."""

    source_path: Path
    relative_path: str


@dataclass(frozen=True, slots=True)
class CopyTask:
    """멀티프로세스로 복사할 파일 작업 단위입니다."""

    source_path: Path
    target_path: Path
    display_path: str
    size_bytes: int


class ProgressBar:
    """터미널에 파일 복사 진행률을 한 줄로 표시합니다."""

    def __init__(self, *, total_bytes: int, total_files: int, enabled: bool) -> None:
        self._total_bytes = max(total_bytes, 0)
        self._total_files = max(total_files, 0)
        self._enabled = enabled
        self._copied_bytes = 0
        self._copied_files = 0
        self._last_rendered_percent = -1
        self._last_message_length = 0

    def advance(self, copied_bytes: int, *, current_file: str) -> None:
        """복사된 바이트를 누적하고 진행률을 출력합니다."""
        if not self._enabled:
            return
        self._copied_bytes += copied_bytes
        self._render(current_file=current_file, force=False)

    def complete_file(self, *, current_file: str) -> None:
        """파일 하나의 복사가 끝났음을 표시합니다."""
        if not self._enabled:
            return
        self._copied_files += 1
        self._render(current_file=current_file, force=True)

    def finish(self) -> None:
        """진행률 표시 줄을 종료합니다."""
        if not self._enabled:
            return
        self._render(current_file="done", force=True)
        print()

    def _render(self, *, current_file: str, force: bool) -> None:
        percent = (
            100
            if self._total_bytes == 0
            else min(100, int(self._copied_bytes * 100 / self._total_bytes))
        )
        if not force and percent == self._last_rendered_percent:
            return
        self._last_rendered_percent = percent
        filled = int(percent / 5)
        bar = "#" * filled + "-" * (20 - filled)
        current_name = PurePosixPath(current_file).name[:34]
        message = (
            f"\r[{bar}] {percent:3d}% "
            f"{_format_bytes(self._copied_bytes)}/{_format_bytes(self._total_bytes)} "
            f"({self._copied_files}/{self._total_files} files) {current_name}"
        )
        padding = " " * max(0, self._last_message_length - len(message))
        self._last_message_length = len(message)
        print(f"{message}{padding}", end="", flush=True)


def _format_bytes(value: int) -> str:
    """바이트 값을 진행률 표시에 적합한 문자열로 변환합니다."""
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    if value < 1024 * 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    return f"{value / (1024 * 1024 * 1024):.1f} GB"


def _normalize_relative_path(value: str) -> str:
    """절대 경로와 상위 디렉터리 참조를 제거한 POSIX 상대 경로를 반환합니다."""
    parts = [
        part.strip()
        for part in PurePosixPath(value.replace("\\", "/")).parts
        if part.strip() and part not in {".", "..", "/"}
    ]
    return "/".join(parts) if parts else "uploaded-file"


def _next_available_path(path: str, reserved: set[str]) -> str:
    """이미 존재하는 relative_path면 파일명에 번호를 붙여 충돌을 피합니다."""
    if path not in reserved:
        return path

    target = PurePosixPath(path)
    stem = target.stem or target.name
    suffix = target.suffix
    parent = str(target.parent)
    index = 2

    while True:
        name = f"{stem} ({index}){suffix}"
        candidate = name if parent == "." else f"{parent}/{name}"
        if candidate not in reserved:
            return candidate
        index += 1


def _iter_import_files(
    source: Path,
    *,
    include_root_folder: bool,
    include_all: bool,
) -> list[ImportFile]:
    """입력 파일/폴더에서 지원 가능한 파일 목록을 수집합니다."""
    if source.is_file():
        if not include_all and source.suffix.lower() not in SUPPORTED_SUFFIXES:
            return []
        return [ImportFile(source_path=source, relative_path=source.name)]

    root_prefix = source.name if include_root_folder else ""
    files: list[ImportFile] = []
    for file_path in sorted(path for path in source.rglob("*") if path.is_file()):
        if not include_all and file_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        relative = file_path.relative_to(source).as_posix()
        if root_prefix:
            relative = f"{root_prefix}/{relative}"
        files.append(
            ImportFile(
                source_path=file_path,
                relative_path=_normalize_relative_path(relative),
            )
        )
    return files


def _load_existing_items() -> tuple[set[str], dict[str, str]]:
    """DB에 이미 등록된 relative_path와 폴더 path-id 매핑을 조회합니다."""
    with SessionLocal() as db:
        rows = db.execute(
            select(
                DataSourceItemOrm.id,
                DataSourceItemOrm.item_type,
                DataSourceItemOrm.relative_path,
            )
        ).all()
    reserved_paths = {relative_path for _, _, relative_path in rows}
    folder_id_by_path = {
        relative_path: item_id
        for item_id, item_type, relative_path in rows
        if item_type == "folder"
    }
    return reserved_paths, folder_id_by_path


def _build_rows(
    files: list[ImportFile],
    reserved_paths: set[str],
    folder_id_by_path: dict[str, str],
    *,
    copy_files: bool,
    progress: ProgressBar,
    workers: int,
) -> tuple[list[DataSourceItemOrm], list[CopyTask]]:
    """파일 목록에서 폴더/file DB row와 파일 복사 작업을 생성합니다."""
    DATA_SOURCE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    rows: list[DataSourceItemOrm] = []
    copy_tasks: list[CopyTask] = []
    path_to_id: dict[str, str] = dict(folder_id_by_path)

    for file_index, file in enumerate(files):
        relative_path = _next_available_path(file.relative_path, reserved_paths)
        reserved_paths.add(relative_path)
        parts = relative_path.split("/")
        parent_id: str | None = None
        ancestor_parts: list[str] = []

        for depth, folder_name in enumerate(parts[:-1]):
            ancestor_parts.append(folder_name)
            folder_path = "/".join(ancestor_parts)
            if folder_path in path_to_id:
                parent_id = path_to_id[folder_path]
                continue

            folder_id = str(uuid4())
            path_to_id[folder_path] = folder_id
            rows.append(
                DataSourceItemOrm(
                    id=folder_id,
                    parent_id=parent_id,
                    item_type="folder",
                    name=folder_name,
                    relative_path=folder_path,
                    depth=depth,
                    sort_order=len(rows),
                    content_type=None,
                    size_bytes=None,
                    storage_path=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            parent_id = folder_id

        file_id = str(uuid4())
        filename = PurePosixPath(parts[-1]).name or "uploaded-file"
        storage_path = DATA_SOURCE_STORAGE_DIR / f"{file_id}__{filename}"
        if copy_files:
            if workers <= 1:
                _copy_file_with_progress(
                    file.source_path,
                    storage_path,
                    progress=progress,
                    display_path=relative_path,
                )
            else:
                copy_tasks.append(
                    CopyTask(
                        source_path=file.source_path,
                        target_path=storage_path,
                        display_path=relative_path,
                        size_bytes=file.source_path.stat().st_size,
                    )
                )
        content_type, _ = mimetypes.guess_type(filename)
        rows.append(
            DataSourceItemOrm(
                id=file_id,
                parent_id=parent_id,
                item_type="file",
                name=filename,
                relative_path=relative_path,
                depth=len(parts) - 1,
                sort_order=file_index,
                content_type=content_type,
                size_bytes=file.source_path.stat().st_size,
                storage_path=str(storage_path),
                created_at=now,
                updated_at=now,
            )
        )

    return rows, copy_tasks


def _copy_file_with_progress(
    source_path: Path,
    target_path: Path,
    *,
    progress: ProgressBar,
    display_path: str,
) -> None:
    """대용량 파일을 chunk 단위로 복사하며 진행률을 갱신합니다."""
    with source_path.open("rb") as source_file, target_path.open("wb") as target_file:
        while True:
            chunk = source_file.read(COPY_CHUNK_SIZE)
            if not chunk:
                break
            target_file.write(chunk)
            progress.advance(len(chunk), current_file=display_path)
    progress.complete_file(current_file=display_path)


def _copy_file_worker(task: CopyTask) -> CopyTask:
    """자식 프로세스에서 파일 하나를 chunk 단위로 복사합니다."""
    with task.source_path.open("rb") as source_file, task.target_path.open("wb") as target_file:
        while True:
            chunk = source_file.read(COPY_CHUNK_SIZE)
            if not chunk:
                break
            target_file.write(chunk)
    return task


def _copy_files_in_parallel(
    tasks: list[CopyTask],
    *,
    workers: int,
    progress: ProgressBar,
) -> None:
    """여러 프로세스로 파일 복사를 수행하고 완료 기준 진행률을 갱신합니다."""
    if not tasks:
        return

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_copy_file_worker, task) for task in tasks]
        for future in as_completed(futures):
            task = future.result()
            progress.advance(task.size_bytes, current_file=task.display_path)
            progress.complete_file(current_file=task.display_path)


def import_data_sources(
    source: Path,
    *,
    include_root_folder: bool,
    include_all: bool,
    dry_run: bool,
    show_progress: bool,
    workers: int,
) -> int:
    """로컬 파일/폴더를 원천 데이터 저장소와 DB에 적재합니다."""
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)

    init_database()
    files = _iter_import_files(
        source,
        include_root_folder=include_root_folder,
        include_all=include_all,
    )
    if not files:
        print("No supported data files found.")
        return 0

    reserved_paths, folder_id_by_path = _load_existing_items()
    progress = ProgressBar(
        total_bytes=sum(file.source_path.stat().st_size for file in files),
        total_files=len(files),
        enabled=show_progress and not dry_run,
    )
    rows, copy_tasks = _build_rows(
        files,
        reserved_paths,
        folder_id_by_path,
        copy_files=not dry_run,
        progress=progress,
        workers=max(1, workers),
    )
    _copy_files_in_parallel(
        copy_tasks,
        workers=max(1, workers),
        progress=progress,
    )
    progress.finish()
    if dry_run:
        for row in rows:
            print(f"[dry-run] {row.item_type}: {row.relative_path}")
        return len(rows)

    file_count = sum(1 for row in rows if row.item_type == "file")
    folder_count = sum(1 for row in rows if row.item_type == "folder")
    with SessionLocal() as db:
        db.add_all(rows)
        db.commit()

    print(f"Imported {file_count} files and {folder_count} folders.")
    return len(rows)


def parse_args() -> argparse.Namespace:
    """CLI 인자를 파싱합니다."""
    parser = argparse.ArgumentParser(
        description="Import local data files/folders into data_source_items for development.",
    )
    parser.add_argument("source", type=Path, help="적재할 로컬 파일 또는 폴더 경로")
    parser.add_argument(
        "--no-root-folder",
        action="store_true",
        help="폴더 적재 시 최상위 폴더명을 relative_path에 포함하지 않습니다.",
    )
    parser.add_argument(
        "--include-all",
        action="store_true",
        help="지원 확장자 필터를 끄고 모든 파일을 적재합니다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB 저장 없이 생성될 row 경로만 출력합니다.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="파일 복사 진행률 표시를 끕니다.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="파일 복사에 사용할 프로세스 수입니다. 기본값은 1입니다.",
    )
    return parser.parse_args()


def main() -> None:
    """개발용 원천 데이터 적재 CLI entrypoint입니다."""
    args = parse_args()
    import_data_sources(
        args.source,
        include_root_folder=not args.no_root_folder,
        include_all=args.include_all,
        dry_run=args.dry_run,
        show_progress=not args.no_progress,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
