from typing import Protocol


class DatasetMetadataRecord(Protocol):
    """데이터셋 조회 usecase가 필요로 하는 메타데이터 record 인터페이스입니다."""

    # ORM 구현 세부사항 대신 usecase가 실제로 읽는 필드만 노출합니다.
    id: str
    storage_path: str | None
    preview: dict[str, object] | None
    profile: dict[str, object] | None


class DatasetMetadataReader(Protocol):
    """데이터셋 메타데이터 조회 port입니다."""

    def get_or_raise(self, dataset_id: str) -> DatasetMetadataRecord:
        """데이터셋 메타데이터를 조회하고 없으면 KeyError를 발생시킵니다."""
        ...
