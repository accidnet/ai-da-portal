from functools import lru_cache

from features.data_sources.application.usecase import DataSourceUsecase
from features.data_sources.infrastructure.repositories import DataSourceRepository


@lru_cache
def get_data_source_repository() -> DataSourceRepository:
    """원천 데이터 feature 전용 repository dependency를 반환합니다."""
    return DataSourceRepository()


@lru_cache
def get_data_source_usecase() -> DataSourceUsecase:
    """원천 데이터 feature 전용 usecase dependency를 반환합니다."""
    return DataSourceUsecase(repository=get_data_source_repository())
