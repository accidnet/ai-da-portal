from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from features.workspaces.infrastructure.orm import WorkspaceOrm
from infrastructure.db.models import (
    DatasetOrm,
    DatasetSourceOrm,
    DatasetSourceProfileOrm,
    UserMessageDatasetLinkOrm,
    WorkspaceDatasetLinkOrm,
)
from infrastructure.db.session import SessionLocal


@dataclass(frozen=True, slots=True)
class DatasetSourceRecord:
    """데이터셋과 원천 데이터 업로드 row의 연결 record입니다."""

    id: str
    source_ref_id: str | None
    created_at: datetime
    row_count: int = 0
    column_count: int = 0
    preview: dict[str, object] | None = None
    profile: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    """서비스가 사용하는 데이터셋 정의 조회 record입니다."""

    id: str
    name: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
    sources: list[DatasetSourceRecord] = field(default_factory=list)

    @property
    def filename(self) -> str:
        """기존 API 호환용 표시 파일명을 반환합니다."""
        return self.name or "dataset"

    @property
    def storage_path(self) -> str | None:
        """데이터셋은 원천 데이터 업로드 row를 통해 파일 경로를 조회합니다."""
        return None

    @property
    def preview(self) -> None:
        """preview는 원천 데이터 파일을 기준으로 application service에서 계산합니다."""
        return None

    @property
    def profile(self) -> None:
        """profile은 원천 데이터 파일을 기준으로 application service에서 계산합니다."""
        return None


class DatasetRepository:
    """데이터셋 정의와 원천 데이터 연결 ORM 조회/영속화를 담당합니다."""

    def create(
        self,
        *,
        dataset_id: str,
        created_at: datetime,
        name: str | None = None,
        description: str | None = None,
        sources: list[dict[str, object]] | None = None,
        source_profiles: list[dict[str, object]] | None = None,
    ) -> DatasetRecord:
        """새 데이터셋 정의와 원천 데이터 연결 row를 저장합니다."""
        with SessionLocal() as db:
            dataset = DatasetOrm(
                id=dataset_id,
                name=name,
                description=description,
                created_at=created_at,
                updated_at=created_at,
            )
            db.add(dataset)
            source_id_by_ref: dict[str, str] = {}
            source_rows: list[DatasetSourceOrm] = []
            for source in sources or []:
                source_id = str(source.get("id") or uuid4())
                source_ref_id = (
                    str(source["source_ref_id"])
                    if source.get("source_ref_id") is not None
                    else None
                )
                source_rows.append(
                    DatasetSourceOrm(
                        id=source_id,
                        dataset_id=dataset_id,
                        source_ref_id=source_ref_id,
                        created_at=created_at,
                    )
                )
                if source_ref_id is not None:
                    source_id_by_ref[source_ref_id] = source_id
            db.add_all(source_rows)

            profile_rows: list[DatasetSourceProfileOrm] = []
            for profile in source_profiles or []:
                dataset_source_id = profile.get("dataset_source_id")
                if dataset_source_id is None and profile.get("source_ref_id") is not None:
                    dataset_source_id = source_id_by_ref.get(str(profile["source_ref_id"]))
                if dataset_source_id is None:
                    continue
                profile_rows.append(
                    DatasetSourceProfileOrm(
                        id=str(profile.get("id") or uuid4()),
                        dataset_source_id=str(dataset_source_id),
                        row_count=int(profile.get("row_count") or 0),
                        column_count=int(profile.get("column_count") or 0),
                        preview=profile.get("preview"),
                        profile=profile.get("profile"),
                        created_at=created_at,
                    )
                )
            db.add_all(profile_rows)
            db.commit()
            return self.get_or_raise(dataset_id)

    def list_datasets(self) -> list[DatasetRecord]:
        """최신 생성 순서로 데이터셋 정의 목록을 조회합니다."""
        statement = (
            select(DatasetOrm)
            .options(joinedload(DatasetOrm.sources).joinedload(DatasetSourceOrm.profile))
            .order_by(DatasetOrm.created_at.desc())
        )
        with SessionLocal() as db:
            datasets = list(db.scalars(statement).unique().all())
            return [self._to_record(dataset) for dataset in datasets]

    def get(self, dataset_id: str) -> DatasetRecord | None:
        """데이터셋 ID로 데이터셋 정의를 조회합니다."""
        statement = (
            select(DatasetOrm)
            .options(joinedload(DatasetOrm.sources).joinedload(DatasetSourceOrm.profile))
            .where(DatasetOrm.id == dataset_id)
        )
        with SessionLocal() as db:
            dataset = db.scalars(statement).unique().first()
            return self._to_record(dataset) if dataset is not None else None

    def get_or_raise(self, dataset_id: str) -> DatasetRecord:
        """데이터셋 정의를 조회하고 없으면 KeyError를 발생시킵니다."""
        dataset = self.get(dataset_id)
        if dataset is None:
            raise KeyError(dataset_id)
        return dataset

    def get_latest(self) -> DatasetRecord | None:
        """가장 최근에 생성된 데이터셋 정의를 조회합니다."""
        statement = (
            select(DatasetOrm)
            .options(joinedload(DatasetOrm.sources).joinedload(DatasetSourceOrm.profile))
            .order_by(DatasetOrm.created_at.desc())
            .limit(1)
        )
        with SessionLocal() as db:
            dataset = db.scalars(statement).unique().first()
            return self._to_record(dataset) if dataset is not None else None

    def find_latest_by_filename(self, filename: str) -> DatasetRecord | None:
        """파일명 기반 조회는 원천 데이터 중심 구조에서 지원하지 않습니다."""
        del filename
        return None

    def delete(self, dataset_id: str) -> None:
        """데이터셋 정의와 원천 연결 row를 삭제합니다."""
        with SessionLocal() as db:
            dataset = db.scalar(select(DatasetOrm).where(DatasetOrm.id == dataset_id))
            if dataset is None:
                raise KeyError(dataset_id)
            # SQLite FK 설정 차이에 영향받지 않도록 참조 링크를 먼저 제거합니다.
            db.execute(
                delete(WorkspaceDatasetLinkOrm).where(
                    WorkspaceDatasetLinkOrm.dataset_id == dataset_id
                )
            )
            db.execute(
                delete(UserMessageDatasetLinkOrm).where(
                    UserMessageDatasetLinkOrm.dataset_id == dataset_id
                )
            )
            db.delete(dataset)
            db.commit()

    def list_workspace_links(self, dataset_id: str) -> list[tuple[str, datetime]]:
        """데이터셋이 연결된 워크스페이스 목록을 최신 연결순으로 조회합니다."""
        with SessionLocal() as db:
            return list(
                db.execute(
                    select(
                        WorkspaceDatasetLinkOrm.workspace_id,
                        WorkspaceDatasetLinkOrm.linked_at,
                    )
                    .join(
                        WorkspaceOrm,
                        WorkspaceOrm.id == WorkspaceDatasetLinkOrm.workspace_id,
                    )
                    .where(WorkspaceDatasetLinkOrm.dataset_id == dataset_id)
                    .order_by(WorkspaceDatasetLinkOrm.linked_at.desc())
                ).all()
            )

    def _to_record(self, dataset: DatasetOrm) -> DatasetRecord:
        """ORM aggregate를 조회 record로 변환합니다."""
        sources = [
            DatasetSourceRecord(
                id=source.id,
                source_ref_id=source.source_ref_id,
                created_at=source.created_at,
                row_count=source.profile.row_count if source.profile else 0,
                column_count=source.profile.column_count if source.profile else 0,
                preview=source.profile.preview if source.profile else None,
                profile=source.profile.profile if source.profile else None,
            )
            for source in dataset.sources
        ]
        return DatasetRecord(
            id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
            sources=sources,
        )
