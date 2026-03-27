from domain.shared import DatasetColumnProfile, DatasetProfilePayload


def build_placeholder_profile() -> DatasetProfilePayload:
    return DatasetProfilePayload(
        row_count=1200,
        column_count=5,
        columns=[
            DatasetColumnProfile(
                name="date",
                dtype="datetime",
                sample_values=["2025-01-01", "2025-01-02"],
            ),
            DatasetColumnProfile(
                name="spend", dtype="float", sample_values=["1500.0", "2100.5"]
            ),
            DatasetColumnProfile(
                name="new_users", dtype="int", sample_values=["120", "148"]
            ),
        ],
        suggested_prompts=[
            "Plot monthly spend vs new users.",
            "Find anomalies in conversion performance.",
            "Summarize missing values and data quality issues.",
        ],
    )
