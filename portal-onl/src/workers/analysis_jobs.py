import pandas as pd

from domain.analyses.chart_builders import build_analytics_from_dataframe


def run_analysis_job(analysis_id: str, analysis_type: str) -> dict[str, object]:
    dataframe = pd.DataFrame(
        {
            "month": ["Jan", "Feb", "Mar"],
            "value": [15, 60, 100],
        }
    )
    return {
        "analysis_id": analysis_id,
        "analysis_type": analysis_type,
        "analytics": build_analytics_from_dataframe(dataframe, analysis_type).model_dump(),
    }
