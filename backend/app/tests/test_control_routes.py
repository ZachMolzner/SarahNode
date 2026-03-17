from fastapi.testclient import TestClient

from app.main import app


def test_assistant_message_route_accepts_request() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/assistant/messages",
            json={"username": "local-user", "content": "Plan my afternoon", "priority": 1},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "queued"}


def test_legacy_message_route_still_works() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/send",
            json={"username": "local-user", "content": "Legacy path test", "priority": 1},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "queued"}


def test_assistant_state_route_shape() -> None:
    with TestClient(app) as client:
        response = client.get("/api/assistant/state")

    assert response.status_code == 200

    payload = response.json()
    assert "assistant_state" in payload
    assert "latest_reply" in payload
    assert "memory_summary" in payload
