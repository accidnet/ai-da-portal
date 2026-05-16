from typing import Protocol


class DatasetSourceMetadataRecord(Protocol):
    """데이터셋 원천 파일 연결 record 인터페이스입니다."""

    source_ref_id: str | None
    preview: dict[str, object] | None
    profile: dict[str, object] | None


class DatasetMetadataRecord(Protocol):
    """데이터셋 조회 usecase가 필요로 하는 메타데이터 record 인터페이스입니다."""

    # ORM 구현 세부사항 대신 usecase가 실제로 읽는 필드만 노출합니다.
    id: str
    filename: str
    storage_path: str | None
    preview: dict[str, object] | None
    profile: dict[str, object] | None
    sources: list[DatasetSourceMetadataRecord]


class DatasetMetadataReader(Protocol):
    """데이터셋 메타데이터 조회 port입니다."""

    def get_or_raise(self, dataset_id: str) -> DatasetMetadataRecord:
        """데이터셋 메타데이터를 조회하고 없으면 KeyError를 발생시킵니다."""
        ...
