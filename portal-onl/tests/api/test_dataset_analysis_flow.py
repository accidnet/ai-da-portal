from io import BytesIO
from textwrap import dedent

from fastapi.testclient import TestClient

from api.deps import (
    get_analysis_service,
    get_dataset_service,
    get_message_service,
    get_session_service,
)
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
        del dataset_ids
        if "세션 제목 생성기" in system:
            return "마케팅 지표 상관분석"
        return f"GPT reply: {user_message[:80]}"

    def generate_json(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> dict[str, object]:
        del system, dataset_ids
        lowered = user_message.lower()

        template_id = "chart_focus"
        title = "LLM Workspace"
        if "correlation" in lowered or "상관" in lowered:
            template_id = "correlation_focus"
            title = "Correlation Workspace"
        elif "trend" in lowered or "추세" in lowered:
            template_id = "trend_story"
            title = "Trend Workspace"
        elif "anomaly" in lowered or "이상치" in lowered:
            template_id = "anomaly_watch"
            title = "Anomaly Workspace"
        elif "group" in lowered or "compare" in lowered or "채널별" in lowered:
            template_id = "comparison_board"
            title = "Comparison Workspace"

        return {
            "template_id": template_id,
            "title": title,
            "description": "Chosen by fake LLM planner",
            "sections": [
                {"kind": "chart", "chart_index": 0, "title": "Primary Chart"},
                {"kind": "summary_cards", "max_items": 4, "title": "Key Metrics"},
                {"kind": "table", "table_index": 0, "title": "Detail Table"},
                {"kind": "insight", "insight_index": 0, "title": "Recommendation"},
            ],
        }


def _override_message_service() -> MessageService:
    return MessageService(
        llm_client=FakeLlmClient(),
        dataset_service=get_dataset_service(),
        analysis_service=get_analysis_service(),
        session_service=get_session_service(),
    )


def test_uploaded_dataset_preview_profile_and_list() -> None:
    with TestClient(app) as client:
        dataset = _upload_sample_csv(client)

        listed = client.get("/api/v1/datasets")
        assert listed.status_code == 200
        listed_item = next(
            item for item in listed.json() if item["id"] == dataset["id"]
        )
        assert listed_item["row_count"] == 12
        assert listed_item["column_count"] == 4
        assert listed_item["linked_session_count"] == 0
        assert listed_item["linked_session_ids"] == []
        assert listed_item["latest_used_at"] is None

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


def test_dataset_delete_blocks_linked_sessions_and_allows_unlinked_dataset() -> None:
    with TestClient(app) as client:
        linked_dataset = _upload_sample_csv(client)

        attach = client.post(
            "/api/v1/sessions/delete-guard-session/datasets",
            json={"dataset_id": linked_dataset["id"]},
        )
        assert attach.status_code == 201

        listed = client.get("/api/v1/datasets")
        assert listed.status_code == 200
        linked_item = next(
            item for item in listed.json() if item["id"] == linked_dataset["id"]
        )
        assert linked_item["linked_session_count"] == 1
        assert linked_item["linked_session_ids"] == ["delete-guard-session"]
        assert linked_item["latest_used_at"] is not None

        blocked_delete = client.delete(f"/api/v1/datasets/{linked_dataset['id']}")
        assert blocked_delete.status_code == 409

        detached = client.delete(
            f"/api/v1/sessions/delete-guard-session/datasets/{linked_dataset['id']}"
        )
        assert detached.status_code == 200
        assert detached.json()["dataset_ids"] == []

        deleted = client.delete(f"/api/v1/datasets/{linked_dataset['id']}")
        assert deleted.status_code == 200
        assert deleted.json() == {"id": linked_dataset["id"], "deleted": True}

        missing = client.get(f"/api/v1/datasets/{linked_dataset['id']}")
        assert missing.status_code == 404


def test_dataset_upload_accepts_optional_session_id_and_links_snapshot() -> None:
    with TestClient(app) as client:
        csv_content = dedent(
            """
            date,channel,spend,new_users
            2025-01-01,social,1500,120
            2025-02-01,search,2100,148
            """
        ).strip()

        response = client.post(
            "/api/v1/datasets/upload",
            data={"session_id": "upload-session"},
            files={
                "file": (
                    "linked_metrics.csv",
                    BytesIO(csv_content.encode("utf-8")),
                    "text/csv",
                )
            },
        )
        assert response.status_code == 201
        dataset = response.json()

        snapshot = client.get("/api/v1/sessions/upload-session/snapshot")
        assert snapshot.status_code == 200
        snapshot_body = snapshot.json()
        assert snapshot_body["dataset_ids"] == [dataset["id"]]
        assert snapshot_body["session"]["preferred_dataset_id"] == dataset["id"]
        assert (
            snapshot_body["datasets"][0]["detail"]["filename"] == "linked_metrics.csv"
        )
        assert snapshot_body["workspace"] is None


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
        assert analysis_body["analytics"]["charts"][0]["id"] == "correlation_scatter"
        assert analysis_body["analytics"]["charts"][0]["type"] == "scatter"
        assert analysis_body["analytics"]["charts"][0]["points"]
        assert analysis_body["workspace"] is not None
        assert analysis_body["workspace"]["template_id"] == "correlation_focus"
        assert analysis_body["workspace"]["sections"]

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
        assert chat_body["workspace"] is not None
        assert chat_body["workspace"]["template_id"] == "correlation_focus"
        assert chat_body["assistant_message"].startswith("GPT reply:")
        assert chat_body["session_title"] == "Marketing performance review"
        assert chat_body["analytics"]["summary_cards"]
        assert chat_body["analytics"]["charts"][0]["id"] == "correlation_scatter"
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
        assert chat_body["workspace"] is not None
        assert chat_body["assistant_message"].startswith("GPT reply:")
        assert chat_body["session_title"] == "마케팅 지표 상관분석"
        assert chat_body["analytics"]["charts"]
        assert chat_body["analytics"]["charts"][0]["id"] == "correlation_scatter"
        assert chat_body["analytics"]["charts"][0]["type"] == "scatter"
    app.dependency_overrides.clear()


def test_analysis_workspace_supports_trend_and_anomaly_templates() -> None:
    app.dependency_overrides[get_message_service] = _override_message_service
    with TestClient(app) as client:
        dataset = _upload_sample_csv(client)

        trend = client.post(
            "/api/v1/analyses",
            json={
                "session_id": "trend-session",
                "dataset_id": dataset["id"],
                "analysis_type": "trend",
                "prompt": "Show the monthly trend for spend.",
            },
        )
        assert trend.status_code == 202
        assert trend.json()["workspace"]["template_id"] == "trend_story"
        assert trend.json()["analytics"]["charts"][0]["id"] == "trend_line"
        assert trend.json()["analytics"]["charts"][0]["type"] == "line"

        anomaly = client.post(
            "/api/v1/analyses",
            json={
                "session_id": "anomaly-session",
                "dataset_id": dataset["id"],
                "analysis_type": "anomaly_detection",
                "prompt": "Detect anomaly rows in spend.",
            },
        )
        assert anomaly.status_code == 202
        assert anomaly.json()["workspace"]["template_id"] == "anomaly_watch"

    app.dependency_overrides.clear()


def test_chat_selects_donut_for_share_questions() -> None:
    app.dependency_overrides[get_message_service] = _override_message_service
    with TestClient(app) as client:
        dataset = _upload_sample_csv(client)

        chat = client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "share-session",
                "message": "채널별 spend 비중을 도넛 형태로 보여줘.",
                "dataset_ids": [dataset["id"]],
            },
        )

        assert chat.status_code == 202
        body = chat.json()
        assert body["analytics"] is not None
        assert body["analytics"]["charts"][0]["id"] == "share_donut"
        assert body["analytics"]["charts"][0]["type"] == "donut"
        assert body["analytics"]["charts"][0]["x"]
        assert body["analytics"]["charts"][0]["series"][0]["data"]

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
        assert body["workspace"] is not None
        assert body["analytics"]["summary_cards"]
        assert body["assistant_message"].startswith("GPT reply:")
        assert body["session_title"] == "marketing_metrics.csv"

        snapshot = client.get("/api/v1/sessions/interaction-session/snapshot")
        assert snapshot.status_code == 200
        snapshot_body = snapshot.json()
        assert snapshot_body["dataset_ids"] == [body["dataset"]["detail"]["id"]]
        assert (
            snapshot_body["datasets"][0]["detail"]["id"]
            == body["dataset"]["detail"]["id"]
        )

    app.dependency_overrides.clear()


def test_session_snapshot_hydrates_messages_datasets_and_workspace() -> None:
    app.dependency_overrides[get_message_service] = _override_message_service
    with TestClient(app) as client:
        dataset = _upload_sample_csv(client)

        analysis = client.post(
            "/api/v1/analyses",
            json={
                "session_id": "snapshot-session",
                "dataset_id": dataset["id"],
                "analysis_type": "trend",
                "prompt": "월별 spend 추세를 요약해줘.",
            },
        )
        assert analysis.status_code == 202
        analysis_body = analysis.json()

        chat = client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "snapshot-session",
                "message": "이 세션의 최신 분석 결과를 짧게 설명해줘.",
                "dataset_ids": [dataset["id"]],
            },
        )
        assert chat.status_code == 202

        snapshot = client.get("/api/v1/sessions/snapshot-session/snapshot")
        assert snapshot.status_code == 200
        snapshot_body = snapshot.json()

        assert snapshot_body["session"]["id"] == "snapshot-session"
        assert snapshot_body["session"]["preferred_dataset_id"] == dataset["id"]
        assert snapshot_body["dataset_ids"] == [dataset["id"]]
        assert len(snapshot_body["messages"]) == 2
        assert snapshot_body["messages"][0]["role"] == "user"
        assert snapshot_body["messages"][1]["role"] == "assistant"
        assert snapshot_body["datasets"][0]["detail"]["id"] == dataset["id"]
        assert snapshot_body["datasets"][0]["preview"]["columns"] == [
            "date",
            "channel",
            "spend",
            "new_users",
        ]
        assert snapshot_body["datasets"][0]["profile"]["profile"]["row_count"] == 12
        assert snapshot_body["analytics"] is not None
        assert snapshot_body["workspace"] is not None
        assert (
            snapshot_body["workspace"]["template_id"]
            == chat.json()["workspace"]["template_id"]
        )
        assert snapshot_body["workspace"]["title"] == chat.json()["workspace"]["title"]

    app.dependency_overrides.clear()


def _override_message_service_with_title_failure() -> MessageService:
    return MessageService(
        llm_client=FailingTitleOnlyClient(),
        dataset_service=get_dataset_service(),
        analysis_service=get_analysis_service(),
        session_service=get_session_service(),
    )


class FailingTitleOnlyClient(FakeLlmClient):
    def generate(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> str:
        if "세션 제목 생성기" in system:
            from infrastructure.llm.client import LlmClientError

            raise LlmClientError("title failure")
        return super().generate(system, user_message, dataset_ids)


class EnvelopeOnlyClient(FakeLlmClient):
    def generate(
        self, system: str, user_message: str, dataset_ids: list[str] | None = None
    ) -> str:
        if "세션 제목 생성기" in system:
            return super().generate(system, user_message, dataset_ids)
        return (
            '{"id":"resp_046a","object":"response","created_at":1775562359,'
            '"status":"completed","output":[],"response":{"output":[]}}'
        )


def _override_message_service_with_envelope_only_client() -> MessageService:
    return MessageService(
        llm_client=EnvelopeOnlyClient(),
        dataset_service=get_dataset_service(),
        analysis_service=get_analysis_service(),
        session_service=get_session_service(),
    )


def test_chat_generates_fallback_session_title_when_llm_title_fails() -> None:
    app.dependency_overrides[get_message_service] = (
        _override_message_service_with_title_failure
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "fallback-title-session",
                "message": "매출과 광고비 추세를 요약하고 다음 분석도 추천해줘. 추가로 채널별 차이도 보고 싶어.",
                "dataset_ids": [],
            },
        )

        assert response.status_code == 202
        body = response.json()
        assert (
            body["session_title"]
            == "매출과 광고비 추세를 요약하고 다음 분석도 추천해줘"
        )

        session = client.get("/api/v1/sessions/fallback-title-session")
        assert session.status_code == 200
        assert session.json()["title"] == body["session_title"]

    app.dependency_overrides.clear()


def test_chat_uses_analysis_fallback_when_llm_returns_response_envelope() -> None:
    app.dependency_overrides[get_message_service] = (
        _override_message_service_with_envelope_only_client
    )
    with TestClient(app) as client:
        dataset = _upload_sample_csv(client)

        response = client.post(
            "/api/v1/chat/messages",
            json={
                "session_id": "envelope-session",
                "message": "spend와 new_users의 관계를 분석해줘.",
                "dataset_ids": [dataset["id"]],
            },
        )

        assert response.status_code == 202
        body = response.json()
        assert body["analytics"] is not None
        assert body["assistant_message"].startswith("백엔드 분석은 완료됐어요.")
        assert '"object":"response"' not in body["assistant_message"]

    app.dependency_overrides.clear()
