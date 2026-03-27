from fastapi.testclient import TestClient

from main import app


def test_cors_allows_local_frontend_origin() -> None:
    client = TestClient(app)
    origin = "http://localhost:5173"

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "GET" in response.headers["access-control-allow-methods"]
