from core.utils import read_string
from features.tools.charts.dto import ChartMeta, ChartPayload, ChartPoint
from features.tools.charts.common import tool_error, tool_success
from shared.integrations.ai.contracts import Function


def tool_definition() -> dict[str, object]:
    """세그먼트 분포 버블 차트 생성 tool 정의를 반환합니다."""
    definition = Function(
        name="build_segment_bubble_chart",
        description=(
            "세그먼트, 고객군, 상품군, 지역, 채널처럼 여러 집단을 비교할 때 사용하는 버블 차트를 생성합니다. "
            "각 집단의 두 핵심 지표를 x/y 위치로, 집단의 규모나 중요도를 버블 크기로 함께 보여줍니다. "
            "단순 순위보다 집단 간 포지셔닝, 군집, 우선순위, 위험-기회 분포를 설명해야 할 때 적합합니다."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "차트 제목입니다.",
                },
                "x_label": {
                    "type": "string",
                    "description": "x축 제목입니다. 집단을 가로 방향으로 구분할 첫 번째 핵심 지표명을 넣습니다.",
                },
                "y_label": {
                    "type": "string",
                    "description": "y축 제목입니다. 집단을 세로 방향으로 구분할 두 번째 핵심 지표명을 넣습니다.",
                },
                "size_label": {
                    "type": ["string", "null"],
                    "description": "버블 크기 기준 설명입니다. 집단 규모나 중요도 기준이 없으면 null입니다.",
                },
                "points": {
                    "type": "array",
                    "description": "비교할 집단별 버블 좌표와 크기 목록입니다.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {
                                "type": "string",
                                "description": "차트에 표시할 집단명입니다.",
                            },
                            "x": {
                                "type": "number",
                                "description": "x축에 표시할 첫 번째 지표 값입니다.",
                            },
                            "y": {
                                "type": "number",
                                "description": "y축에 표시할 두 번째 지표 값입니다.",
                            },
                            "size": {
                                "type": "number",
                                "description": "버블 크기로 표시할 집단 규모 또는 중요도 값입니다.",
                            },
                            "category": {
                                "type": ["string", "null"],
                                "description": "범례 그룹입니다. 별도 그룹이 없으면 label과 같은 값을 넣거나 null을 사용합니다.",
                            },
                        },
                        "required": ["label", "x", "y", "size", "category"],
                        "additionalProperties": False,
                    },
                    "minItems": 1,
                    "maxItems": 30,
                },
            },
            "required": ["title", "x_label", "y_label", "size_label", "points"],
            "additionalProperties": False,
        },
    )
    return definition.model_dump(mode="json", exclude_none=True)


def execute(arguments: dict[str, object]) -> dict[str, object]:
    """LLM function_call arguments만 받아 세그먼트 버블 차트를 생성합니다."""
    try:
        title = _read_required_string(arguments, "title")
        x_label = _read_required_string(arguments, "x_label")
        y_label = _read_required_string(arguments, "y_label")
        points = _read_points(arguments.get("points"))
    except ValueError as exc:
        return tool_error(str(exc))

    chart = ChartPayload(
        id="segment_bubble",
        type="bubble",
        title=title,
        points=points,
        meta=ChartMeta(x_label=x_label, y_label=y_label),
    )
    return tool_success({"chart": chart.model_dump(mode="json")})


def _read_required_string(arguments: dict[str, object], key: str) -> str:
    """필수 문자열 argument를 읽고 누락 시 오류를 발생시킵니다."""
    value = read_string(arguments.get(key))
    if value is None:
        raise ValueError(f"{key} is required.")
    return value


def _read_points(value: object) -> list[ChartPoint]:
    """세그먼트 버블 point 목록을 ChartPoint로 정규화합니다."""
    if not isinstance(value, list) or not value:
        raise ValueError("points must be a non-empty array.")

    points: list[ChartPoint] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("each point must be an object.")
        label = read_string(item.get("label"))
        if label is None:
            raise ValueError("each point needs a label.")
        points.append(
            ChartPoint(
                x=_read_number(item.get("x"), "x"),
                y=_read_number(item.get("y"), "y"),
                size=max(_read_number(item.get("size"), "size"), 0),
                label=label,
                category=read_string(item.get("category")) or label,
            )
        )
    return points


def _read_number(value: object, key: str) -> float:
    """숫자 argument를 float으로 정규화합니다."""
    if not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number.")
    return float(value)
