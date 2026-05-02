from datetime import datetime

from sqlalchemy import select

from infrastructure.db.models import DatasetOrm
from infrastructure.db.session import SessionLocal


class DatasetRepository:
    """업로드 데이터셋 메타데이터의 ORM 조회와 영속화를 담당합니다."""

    def create(
        self,
        *,
        dataset_id: str,
        filename: str,
        storage_path: str,
        created_at: datetime,
    ) -> DatasetOrm:
        """새 데이터셋 메타데이터를 저장하고 로드된 ORM 객체를 반환합니다."""
        with SessionLocal() as db:
            dataset = DatasetOrm(
                id=dataset_id,
                filename=filename,
                storage_path=storage_path,
                created_at=created_at,
            )
            db.add(dataset)
            db.commit()
            db.refresh(dataset)
            return dataset

    def list_datasets(self) -> list[DatasetOrm]:
        """최신 업로드 순서로 데이터셋 목록을 조회합니다."""
        with SessionLocal() as db:
            return list(
                db.scalars(
                    select(DatasetOrm).order_by(DatasetOrm.created_at.desc())
                ).all()
            )

    def get(self, dataset_id: str) -> DatasetOrm | None:
        """데이터셋 ID로 데이터셋 메타데이터를 조회합니다."""
        with SessionLocal() as db:
            return db.scalar(select(DatasetOrm).where(DatasetOrm.id == dataset_id))

    def get_or_raise(self, dataset_id: str) -> DatasetOrm:
        """데이터셋 메타데이터를 조회하고 없으면 KeyError를 발생시킵니다."""
        dataset = self.get(dataset_id)
        if dataset is None:
            raise KeyError(dataset_id)
        return dataset

    def get_latest(self) -> DatasetOrm | None:
        """가장 최근에 업로드된 데이터셋 메타데이터를 조회합니다."""
        with SessionLocal() as db:
            return db.scalar(
                select(DatasetOrm).order_by(DatasetOrm.created_at.desc()).limit(1)
            )

    def find_latest_by_filename(self, filename: str) -> DatasetOrm | None:
        """파일명으로 가장 최근에 업로드된 데이터셋 메타데이터를 조회합니다."""
        with SessionLocal() as db:
            return db.scalar(
                select(DatasetOrm)
                .where(DatasetOrm.filename == filename)
                .order_by(DatasetOrm.created_at.desc())
                .limit(1)
            )

    def delete(self, dataset_id: str) -> None:
        """데이터셋 메타데이터를 삭제합니다."""
        with SessionLocal() as db:
            dataset = db.scalar(select(DatasetOrm).where(DatasetOrm.id == dataset_id))
            if dataset is None:
                raise KeyError(dataset_id)
            db.delete(dataset)
            db.commit()
