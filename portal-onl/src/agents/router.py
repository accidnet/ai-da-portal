from agents.state import AgentRoute


ANALYSIS_KEYWORDS = {
    "analyze",
    "analysis",
    "chart",
    "visualize",
    "correlation",
    "trend",
    "anomaly",
}
DATASET_KEYWORDS = {"csv", "xlsx", "upload", "dataset", "file", "table"}


def route_message(message: str, has_dataset: bool) -> AgentRoute:
    lowered = message.lower()
    if has_dataset or any(keyword in lowered for keyword in DATASET_KEYWORDS):
        return "dataset_analysis"
    if any(keyword in lowered for keyword in ANALYSIS_KEYWORDS):
        return "analysis_request"
    return "conversation"
