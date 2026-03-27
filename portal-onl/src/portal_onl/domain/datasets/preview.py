def build_placeholder_preview() -> tuple[
    list[str], list[dict[str, str | int | float | None]]
]:
    columns = ["date", "channel", "spend", "new_users"]
    rows = [
        {"date": "2025-01-01", "channel": "social", "spend": 1500.0, "new_users": 120},
        {"date": "2025-02-01", "channel": "search", "spend": 2100.5, "new_users": 148},
    ]
    return columns, rows
