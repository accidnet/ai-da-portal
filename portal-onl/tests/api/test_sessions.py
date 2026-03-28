from io import BytesIO
from textwrap import dedent

from fastapi.testclient import TestClient

from main import app


def _upload_dataset(
    client: TestClient, filename: str = "session_metrics.csv"
) -> dict[str, object]:
    csv_content = dedent(
        """
        date,channel,spend,new_users
        2025-01-01,social,1500,120
        2025-02-01,search,2100,148
        """
    ).strip()
    response = client.post(
        "/api/v1/datasets/upload",
        files={
            "file": (
                filename,
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        },
    )
    assert response.status_code == 201
    return response.json()


def test_sessions_create_list_and_get() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/sessions", json={"title": "ChatGPT linked session"}
        )
        assert created.status_code == 201
        session = created.json()
        assert session["title"] == "ChatGPT linked session"
        assert session["created_at"]
        assert session["preferred_dataset_id"] is None
        assert session["message_count"] == 0
        assert session["dataset_count"] == 0
        assert session["last_dataset"] is None

        listed = client.get("/api/v1/sessions")
        assert listed.status_code == 200
        matched = next(item for item in listed.json() if item["id"] == session["id"])
        assert matched["title"] == "ChatGPT linked session"
        assert matched["created_at"]
        assert matched["preferred_dataset_id"] is None
        assert matched["message_count"] == 0
        assert matched["dataset_count"] == 0
        assert matched["last_dataset"] is None

        fetched = client.get(f"/api/v1/sessions/{session['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == session["id"]
        assert fetched.json()["preferred_dataset_id"] is None


def test_session_snapshot_returns_not_found_for_unknown_session() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/unknown-session/snapshot")
        assert response.status_code == 404


def test_session_update_attach_detach_and_delete_flow() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/sessions", json={"title": "Original session title"}
        )
        assert created.status_code == 201
        session = created.json()

        dataset_a = _upload_dataset(client, filename="a_metrics.csv")
        dataset_b = _upload_dataset(client, filename="b_metrics.csv")

        updated = client.patch(
            f"/api/v1/sessions/{session['id']}",
            json={"title": "  Updated   session title  "},
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Updated session title"

        attached_a = client.post(
            f"/api/v1/sessions/{session['id']}/datasets",
            json={"dataset_id": dataset_a["id"]},
        )
        assert attached_a.status_code == 201
        assert attached_a.json() == {
            "session_id": session["id"],
            "dataset_ids": [dataset_a["id"]],
        }

        fetched_after_attach_a = client.get(f"/api/v1/sessions/{session['id']}")
        assert fetched_after_attach_a.status_code == 200
        assert fetched_after_attach_a.json()["preferred_dataset_id"] == dataset_a["id"]

        attached_b = client.post(
            f"/api/v1/sessions/{session['id']}/datasets",
            json={"dataset_id": dataset_b["id"]},
        )
        assert attached_b.status_code == 201
        assert attached_b.json() == {
            "session_id": session["id"],
            "dataset_ids": [dataset_b["id"], dataset_a["id"]],
        }

        fetched = client.get(f"/api/v1/sessions/{session['id']}")
        assert fetched.status_code == 200
        fetched_body = fetched.json()
        assert fetched_body["dataset_count"] == 2
        assert fetched_body["message_count"] == 0
        assert fetched_body["preferred_dataset_id"] == dataset_a["id"]
        assert fetched_body["last_dataset"] == {
            "id": dataset_b["id"],
            "filename": "b_metrics.csv",
        }

        preferred_updated = client.patch(
            f"/api/v1/sessions/{session['id']}",
            json={"preferred_dataset_id": dataset_b["id"]},
        )
        assert preferred_updated.status_code == 200
        assert preferred_updated.json()["preferred_dataset_id"] == dataset_b["id"]

        missing_body = client.patch(f"/api/v1/sessions/{session['id']}", json={})
        assert missing_body.status_code == 400

        invalid_preferred = client.patch(
            f"/api/v1/sessions/{session['id']}",
            json={"preferred_dataset_id": "not-linked"},
        )
        assert invalid_preferred.status_code == 400

        detached = client.delete(
            f"/api/v1/sessions/{session['id']}/datasets/{dataset_b['id']}"
        )
        assert detached.status_code == 200
        assert detached.json() == {
            "session_id": session["id"],
            "dataset_ids": [dataset_a["id"]],
        }

        fetched_after_detach = client.get(f"/api/v1/sessions/{session['id']}")
        assert fetched_after_detach.status_code == 200
        assert fetched_after_detach.json()["preferred_dataset_id"] == dataset_a["id"]

        listed = client.get("/api/v1/sessions")
        assert listed.status_code == 200
        listed_body = next(
            item for item in listed.json() if item["id"] == session["id"]
        )
        assert listed_body["dataset_count"] == 1
        assert listed_body["last_dataset"] == {
            "id": dataset_a["id"],
            "filename": "a_metrics.csv",
        }

        deleted = client.delete(f"/api/v1/sessions/{session['id']}")
        assert deleted.status_code == 200
        assert deleted.json() == {"id": session["id"], "deleted": True}

        missing = client.get(f"/api/v1/sessions/{session['id']}")
        assert missing.status_code == 404
