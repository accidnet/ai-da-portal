from agents.state import AgentRoute


ANALYSIS_KEYWORDS = {
    "analyze",
    "analysis",
    "chart",
    "visualize",
    "visualise",
    "graph",
    "correlation",
    "trend",
    "anomaly",
    "outlier",
    "forecast",
    "segment",
    "compare",
    "breakdown",
    "요약",
    "분석",
    "시각화",
    "그래프",
    "차트",
    "상관",
    "추세",
    "이상치",
    "비교",
    "예측",
}
DATASET_KEYWORDS = {
    "csv",
    "xlsx",
    "xls",
    "json",
    "tsv",
    "upload",
    "dataset",
    "file",
    "table",
    "column",
    "row",
    "schema",
    "데이터",
    "데이터셋",
    "파일",
    "업로드",
    "컬럼",
    "열",
    "행",
}


def route_message(message: str, has_dataset: bool) -> AgentRoute:
    lowered = message.lower().strip()

    if has_dataset:
        if _contains_any(lowered, ANALYSIS_KEYWORDS):
            return "analysis_request"
        return "dataset_analysis"

    if _contains_any(lowered, DATASET_KEYWORDS):
        return "dataset_analysis"
    if _contains_any(lowered, ANALYSIS_KEYWORDS):
        return "analysis_request"
    return "conversation"


def _contains_any(message: str, keywords: set[str]) -> bool:
    return any(keyword in message for keyword in keywords)
