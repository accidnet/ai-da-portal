from portal_onl.domain.datasets.profiling import build_placeholder_profile


def run_dataset_profile(dataset_id: str) -> dict[str, object]:
    return {
        "dataset_id": dataset_id,
        "profile": build_placeholder_profile().model_dump(),
    }
