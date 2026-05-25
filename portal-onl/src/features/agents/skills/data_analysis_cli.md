# Skill: Data Analysis CLI

워크스페이스 CLI로 DuckDB, Python, pandas/polars 기반 데이터 분석을 수행할 때 사용합니다. 목적은 큰 데이터를 LLM input item에 직접 싣지 않고, 파일 기반 산출물과 작은 요약만으로 멀티턴 분석을 이어가는 것입니다.

## 사용 시점

- 원천 데이터가 크거나, SQL 결과가 수십 행을 넘어갈 수 있는 경우
- DuckDB SQL, Python 스크립트, pandas/polars, scikit-learn 등으로 중간 산출물을 만들어야 하는 경우
- 후속 턴에서 같은 결과를 다시 조회하거나 추가 분석할 가능성이 있는 경우
- `run_workspace_cli_command`를 사용할 수 있고 워크스페이스 로컬 저장소가 제공된 경우
- DuckDB SQL을 직접 실행하는 전용 function tool 대신 CLI 기반 분석 경로를 사용해야 하는 경우

## 핵심 규칙

- 큰 row 결과, 전체 DataFrame, 긴 JSON/CSV 본문을 stdout에 출력하지 않습니다.
- 원본 또는 중간 결과는 워크스페이스 내부의 `artifacts/`, `analysis/`, `tmp/` 같은 목적이 드러나는 폴더에 parquet, csv, json, md 파일로 저장합니다.
- CLI stdout에는 `result_id`, 저장 경로, row/column count, schema, 주요 요약, 최대 5~20행 preview만 JSON 또는 짧은 텍스트로 출력합니다.
- `run_workspace_cli_command.max_output_bytes`는 특별한 이유가 없으면 12000 이하로 지정합니다.
- 긴 문자열, JSON blob, 본문 컬럼은 preview에서 제외하거나 200자 이내로 축약합니다.
- 후속 분석은 저장된 parquet/csv 파일을 다시 DuckDB나 Python으로 부분 조회해서 수행합니다.
- 데이터 구조 확인에는 `inspect_dataset_context`를 먼저 사용할 수 있지만, 큰 결과 생성과 분석 계산은 CLI에서 파일 기반으로 수행합니다.

## 권장 workflow

1. `list_files` 또는 데이터셋/source context로 입력 파일과 워크스페이스 위치를 확인합니다.
2. CLI로 DuckDB/Python 스크립트를 실행하되, 결과 전체는 파일로 저장합니다.
3. stdout에는 작은 manifest만 반환합니다.
4. 추가 확인이 필요하면 저장된 파일에 대해 필터, 집계, 샘플링 쿼리를 다시 실행합니다.
5. 최종 답변에는 핵심 결과와 사용자가 확인할 산출물 경로만 간결하게 언급합니다.

## stdout manifest 예시

```json
{
  "result_id": "sales_summary_20260524_001",
  "path": "analysis/sales_summary_20260524_001.parquet",
  "row_count": 128430,
  "column_count": 12,
  "columns": [
    { "name": "order_date", "type": "DATE" },
    { "name": "amount", "type": "DOUBLE" }
  ],
  "preview_rows": 10,
  "truncated": true,
  "notes": "전체 결과는 parquet 파일에 저장됨"
}
```

## DuckDB CLI/Python 패턴

- DuckDB SQL은 `COPY (...) TO 'path.parquet' (FORMAT PARQUET)` 형태를 우선 사용합니다.
- Python에서 DataFrame을 출력하지 말고 `df.head(10).to_dict(...)`, `df.shape`, `df.dtypes` 정도만 출력합니다.
- 통계 요약은 별도 `summary.json` 또는 `summary.md`로 저장하고 stdout에는 경로와 핵심 수치만 둡니다.

## 금지

- `print(df)`, `print(df.to_json())`, `cat large_file.csv`, `SELECT *` 결과 대량 출력
- 파일 저장 없이 대량 결과를 tool response에 직접 반환
- 워크스페이스 경계 밖 경로에 중간 산출물 저장
