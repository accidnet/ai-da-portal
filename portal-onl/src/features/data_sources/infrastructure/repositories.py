from datetime import UTC, datetime

from sqlalchemy import select

from features.data_sources.domain.models import DataSourceItem
from features.data_sources.infrastructure.orm import DataSourceItemOrm
from infrastructure.db.session import SessionLocal


class DataSourceRepository:
    """원천 데이터 파일/폴더 노드의 ORM 작업을 담당합니다."""

    def create_items(self, *, items: list[dict[str, object]]) -> list[DataSourceItem]:
        """flat 파일/폴더 노드를 한 트랜잭션으로 저장합니다."""
        now = datetime.now(UTC)
        with SessionLocal() as db:
            item_rows = [
                DataSourceItemOrm(
                    id=str(item["id"]),
                    parent_id=item["parent_id"],
                    item_type=str(item["item_type"]),
                    name=str(item["name"]),
                    relative_path=str(item["relative_path"]),
                    depth=int(item["depth"]),
                    sort_order=int(item["sort_order"]),
                    content_type=item["content_type"],
                    size_bytes=item["size_bytes"],
                    storage_path=item["storage_path"],
                    created_at=now,
                    updated_at=now,
                )
                for item in items
            ]
            db.add_all(item_rows)
            db.commit()
            for item_row in item_rows:
                db.refresh(item_row)
            return [self._to_item_domain(item_row) for item_row in item_rows]

    def list_items(self) -> list[DataSourceItem]:
        """원천 데이터 파일/폴더 노드를 트리 재현 순서로 조회합니다."""
        statement = select(DataSourceItemOrm).order_by(
            DataSourceItemOrm.depth,
            DataSourceItemOrm.sort_order,
            DataSourceItemOrm.name,
        )
        with SessionLocal() as db:
            items = list(db.scalars(statement).all())
            return [self._to_item_domain(item) for item in items]

    def list_relative_paths(self) -> set[str]:
        """저장된 원천 데이터 노드의 상대 경로 집합을 조회합니다."""
        with SessionLocal() as db:
            rows = db.execute(select(DataSourceItemOrm.relative_path)).all()
            return {relative_path for (relative_path,) in rows}

    def _to_item_domain(self, item: DataSourceItemOrm) -> DataSourceItem:
        """ORM 파일/폴더 노드를 domain 모델로 변환합니다."""
        return DataSourceItem(
            id=item.id,
            parent_id=item.parent_id,
            item_type=item.item_type,
            name=item.name,
            relative_path=item.relative_path,
            depth=item.depth,
            sort_order=item.sort_order,
            content_type=item.content_type,
            size_bytes=item.size_bytes,
            storage_path=item.storage_path,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
