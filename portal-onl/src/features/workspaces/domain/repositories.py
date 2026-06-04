from typing import Protocol

from features.workspaces.domain.models import Workspace


class WorkspaceRepository(Protocol):
    """워크스페이스 저장소가 제공해야 하는 domain port입니다."""

    def create(self, *, workspace_id: str, name: str) -> Workspace:
        """새 워크스페이스를 저장하고 domain 모델을 반환합니다."""
        ...

    def list_workspaces(self) -> list[Workspace]:
        """저장된 워크스페이스 목록을 반환합니다."""
        ...

    def get(self, workspace_id: str) -> Workspace:
        """워크스페이스를 조회하고 없으면 KeyError를 발생시킵니다."""
        ...

    def update(self, *, workspace_id: str, name: str) -> Workspace:
        """워크스페이스 이름을 수정하고 domain 모델을 반환합니다."""
        ...

    def delete(self, workspace_id: str) -> None:
        """워크스페이스를 삭제합니다."""
        ...

    def attach_dataset(self, *, workspace_id: str, dataset_id: str) -> list[str]:
        """워크스페이스에 데이터셋을 연결하고 연결된 데이터셋 ID를 반환합니다."""
        ...

    def detach_dataset(self, *, workspace_id: str, dataset_id: str) -> list[str]:
        """워크스페이스에서 데이터셋 연결을 해제하고 남은 데이터셋 ID를 반환합니다."""
        ...

    def list_dataset_ids(self, workspace_id: str) -> list[str]:
        """워크스페이스에 연결된 데이터셋 ID를 반환합니다."""
        ...
