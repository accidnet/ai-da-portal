from fastapi.testclient import TestClient

from main import app


def test_sessions_create_list_and_get() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/sessions", json={"title": "ChatGPT linked session"}
        )
        assert created.status_code == 201
        session = created.json()
        assert session["title"] == "ChatGPT linked session"

        listed = client.get("/api/v1/sessions")
        assert listed.status_code == 200
        titles = [item["title"] for item in listed.json()]
        assert "ChatGPT linked session" in titles

        fetched = client.get(f"/api/v1/sessions/{session['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == session["id"]


def test_session_snapshot_returns_not_found_for_unknown_session() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/sessions/unknown-session/snapshot")
        assert response.status_code == 404
