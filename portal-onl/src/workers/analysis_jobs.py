from domain.analyses.chart_builders import build_demo_chart


def run_analysis_job(analysis_id: str, analysis_type: str) -> dict[str, object]:
    return {
        "analysis_id": analysis_id,
        "analysis_type": analysis_type,
        "chart": build_demo_chart(analysis_type).model_dump(),
    }
