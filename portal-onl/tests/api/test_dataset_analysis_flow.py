from io import BytesIO
from textwrap import dedent

from fastapi.testclient import TestClient

from api.deps import get_analysis_service, get_dataset_service, get_message_service
from domain.messages.service import MessageService
from infrastructure.llm.client import LlmClient
from main import app


def _upload_sample_csv(client: TestClient) -> dict[str, object]:
    csv_content = dedent(
        """
        date,channel,spend,new_users
        2025-01-01,social,1500,120
        2025-02-01,search,2100,148
        2025-03-01,email,900,95
        2025-04-01,social,1800,136
        2025-05-01,search,2400,160
        2025-06-01,email,1000,102
        2025-07-01,social,2600,175
        2025-08-01,search,2800,180
        2025-09-01,email,1100,108
        2025-10-01,social,3200,230
        2025-11-01,search,2500,165
        2025-12-01,email,1200,111
        """
    ).strip()

    response = client.post(
        "/api/v1/datasets/upload",
        files={
            "file": (
                "marketing_metrics.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    return response.json()


class FakeLlmClient(LlmClient):
    def __init__(self) -> None:
        pass

    def generate(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> str:
        del system, dataset_ids
        return f"GPT reply: {user_message[:80]}"


def _override_message_service() -> MessageService:
    return MessageService(
        llm_client=FakeLlmClient(),
        dataset_service=get_dataset_service(),
        analysis_service=get_analysis_service(),
    )


def test_uploaded_dataset_preview_profile_and_list() -> None:
    with TestClient(app) as client:
        dataset = _upload_sample_csv(client)

        listed = client.get("/api/v1/datasets")
        assert listed.status_code == 200
        assert any(item["id"] == dataset["id"] for item in listed.json())

        preview = client.get(f"/api/v1/datasets/{dataset['id']}/preview")
        assert preview.status_code == 200
        preview_body = preview.json()
        assert preview_body["dataset_id"] == dataset["id"]
        assert preview_body["columns"] == ["date", "channel", "spend", "new_users"]
        assert len(preview_body["rows"]) >= 3

        profile = client.get(f"/api/v1/datasets/{dataset['id']}/profile")
        assert profile.status_code == 200
        profile_body = profile.json()
        assert profile_body["profile"]["row_count"] == 12
        assert profile_body["profile"]["column_count"] == 4
        assert profile_body["profile"]["columns"][0]["dtype"] == "datetime"


def test_analysis_and_chat_use_uploaded_dataset() -> None:
    app.dependency_overrides[get_message_service] = _override_message_service
    with TestClient(app) as client:
        dataset = _upload_sample_csv(client)

        analysis = client.post(
            "/api/v1/analyses",
            json={
                "session_id": "demo-session",
                "dataset_id": dataset["id"],
                "analysis_type": "correlation",
                "prompt": "Show the relationship between spend and new users.",
            },
        )
        assert analysis.status_code == 202
        analysis_body = analysis.json()
        assert analysis_body["dataset_id"] == dataset["id"]
        assert analysis_body["analytics"]["summary_cards"]
        assert analysis_body["analytics"]["charts"]
        assert analysis_body["analytics"]["tables"]
        assert analysis_body["analytics"]["insights"]

        artifacts = client.get(f"/api/v1/analyses/{analysis_body['id']}/artifacts")
        assert artifacts.status_code == 200
        assert artifacts.json()["analysis_id"] == analysis_body["id"]

        chat = client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "demo-session",
                "message": "Analyze the marketing dataset and tell me if spend correlates with new users.",
                "dataset_ids": [dataset["id"]],
            },
        )
        assert chat.status_code == 202
        chat_body = chat.json()
        assert chat_body["analytics"] is not None
        assert chat_body["assistant_message"].startswith("GPT reply:")
        assert chat_body["analytics"]["summary_cards"]
    app.dependency_overrides.clear()


def test_chat_supports_korean_analysis_prompts_with_uploaded_dataset() -> None:
    app.dependency_overrides[get_message_service] = _override_message_service
    with TestClient(app) as client:
        dataset = _upload_sample_csv(client)

        chat = client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "demo-session-ko",
                "message": "이 데이터에서 spend와 new_users의 상관관계를 분석해줘.",
                "dataset_ids": [dataset["id"]],
            },
        )
        assert chat.status_code == 202
        chat_body = chat.json()
        assert chat_body["analytics"] is not None
        assert chat_body["assistant_message"].startswith("GPT reply:")
        assert chat_body["analytics"]["charts"]
    app.dependency_overrides.clear()


def test_chat_interaction_accepts_file_and_message_together() -> None:
    app.dependency_overrides[get_message_service] = _override_message_service
    csv_content = dedent(
        """
        date,channel,spend,new_users
        2025-01-01,social,1500,120
        2025-02-01,search,2100,148
        2025-03-01,email,900,95
        """
    ).strip()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/interactions",
            data={
                "session_id": "interaction-session",
                "message": "이 파일을 업로드하고 바로 분석해줘.",
                "dataset_ids_json": "[]",
            },
            files={
                "file": (
                    "marketing_metrics.csv",
                    BytesIO(csv_content.encode("utf-8")),
                    "text/csv",
                )
            },
        )

        assert response.status_code == 202
        body = response.json()
        assert body["dataset"] is not None
        assert body["dataset"]["detail"]["filename"] == "marketing_metrics.csv"
        assert body["dataset"]["preview"]["columns"] == [
            "date",
            "channel",
            "spend",
            "new_users",
        ]
        assert body["dataset"]["profile"]["profile"]["row_count"] == 3
        assert body["analytics"] is not None
        assert body["analytics"]["summary_cards"]
        assert body["assistant_message"].startswith("GPT reply:")

    app.dependency_overrides.clear()
