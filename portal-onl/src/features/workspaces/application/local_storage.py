import os
import shutil
import time
from pathlib import Path


class WorkspaceLocalStorage:
    """워크스페이스별 agent 로컬 작업 디렉터리를 관리합니다."""

    def __init__(self, *, root_dir: Path, ttl_seconds: int) -> None:
        self._root_dir = root_dir
        self._ttl_seconds = max(ttl_seconds, 0)

    @property
    def root_dir(self) -> Path:
        """워크스페이스 로컬 저장소 루트 경로를 반환합니다."""
        return self._root_dir

    def workspace_dir(self, workspace_id: str) -> Path:
        """워크스페이스 ID에 해당하는 로컬 저장소 경로를 반환합니다."""
        return self._root_dir / workspace_id

    def ensure_workspace(self, workspace_id: str) -> Path:
        """워크스페이스 로컬 저장소를 생성하고 접근 시간을 갱신합니다."""
        workspace_dir = self.workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        self.touch_workspace(workspace_id)
        return workspace_dir

    def delete_workspace(self, workspace_id: str) -> None:
        """워크스페이스 로컬 저장소를 제거합니다."""
        workspace_dir = self.workspace_dir(workspace_id)
        if workspace_dir.exists():
            shutil.rmtree(workspace_dir)

    def touch_workspace(self, workspace_id: str) -> None:
        """주기 정리 기준으로 사용할 워크스페이스 디렉터리 시각을 갱신합니다."""
        workspace_dir = self.workspace_dir(workspace_id)
        if workspace_dir.exists():
            now = time.time()
            workspace_dir.touch(exist_ok=True)
            workspace_dir.chmod(0o700)
            # 일부 플랫폼에서 touch만으로 디렉터리 mtime이 기대대로 변하지 않는 경우를 보정합니다.
            os.utime(workspace_dir, (now, now))

    def cleanup_expired(self) -> list[str]:
        """TTL이 지난 워크스페이스 로컬 저장소를 제거하고 ID 목록을 반환합니다."""
        if self._ttl_seconds <= 0:
            return []

        self._root_dir.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - self._ttl_seconds
        removed_workspace_ids: list[str] = []
        for child in self._root_dir.iterdir():
            if not child.is_dir():
                continue
            try:
                if child.stat().st_mtime >= cutoff:
                    continue
                shutil.rmtree(child)
                removed_workspace_ids.append(child.name)
            except OSError:
                continue
        return removed_workspace_ids

    def resolve_path(self, *, workspace_id: str, relative_path: str | None) -> Path:
        """워크스페이스 저장소 내부 상대 경로를 안전한 절대 경로로 변환합니다."""
        workspace_dir = self.ensure_workspace(workspace_id).resolve()
        requested_path = (workspace_dir / (relative_path or "")).resolve()
        if requested_path != workspace_dir and workspace_dir not in requested_path.parents:
            raise ValueError("Path must stay inside the workspace local storage.")
        return requested_path
