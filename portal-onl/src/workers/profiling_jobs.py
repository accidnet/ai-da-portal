import pandas as pd

from application.datasets.inspection import build_profile_from_dataframe


def run_dataset_profile(dataset_id: str) -> dict[str, object]:
    dataframe = pd.DataFrame(
        {
            "date": ["2025-01-01", "2025-01-02"],
            "spend": [1500, 2100],
            "new_users": [120, 148],
        }
    )
    return {
        "dataset_id": dataset_id,
        "profile": build_profile_from_dataframe(dataframe).model_dump(),
    }
