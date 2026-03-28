from agents.router import route_message


def test_route_message_prefers_analysis_request_for_dataset_with_analysis_intent() -> (
    None
):
    assert (
        route_message("이 데이터의 상관관계를 분석해줘", has_dataset=True)
        == "analysis_request"
    )


def test_route_message_detects_dataset_analysis_without_existing_dataset() -> None:
    assert (
        route_message(
            "CSV 파일 업로드 전에 데이터 컬럼을 먼저 설명해줘", has_dataset=False
        )
        == "dataset_analysis"
    )


def test_route_message_detects_korean_analysis_request_without_dataset() -> None:
    assert (
        route_message("월별 추세를 시각화해줘", has_dataset=False) == "analysis_request"
    )
