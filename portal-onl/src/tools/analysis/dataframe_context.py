from functools import lru_cache

import pandas as pd

from application.datasets.source_loading import load_dataset_dataframe as load_record_dataframe
from infrastructure.db.repositories import DatasetRepository


@lru_cache
def get_dataset_repository() -> DatasetRepository:
    """tool 실행 시 사용할 데이터셋 repository를 생성합니다."""
    # 분석 tool adapter는 dataset_id로 저장 경로만 조회하고 계산은 tool 내부에서 수행합니다.
    return DatasetRepository()


def load_dataset_dataframe(dataset_id: str) -> pd.DataFrame:
    """dataset_id에 해당하는 저장 파일을 DataFrame으로 로드합니다."""
    dataset = get_dataset_repository().get_or_raise(dataset_id)
    return _infer_datetime_columns(load_record_dataframe(dataset))


def _infer_datetime_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """object 컬럼 중 날짜로 해석 가능한 컬럼을 datetime 타입으로 변환합니다."""
    inferred = dataframe.copy()
    for column in inferred.columns:
        series = inferred[column]
        if not pd.api.types.is_object_dtype(series):
            continue
        converted = pd.to_datetime(series, errors="coerce", format="mixed")
        if converted.notna().mean() >= 0.8 and converted.notna().any():
            inferred[column] = converted
    return inferred
