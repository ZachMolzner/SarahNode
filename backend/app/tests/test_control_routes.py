import io

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
    assert "web_browsing" in payload
    assert "last_used_live_web" in payload
    assert "identity_resolution" in payload


def test_voice_event_route_accepts_voice_prefix() -> None:
    with TestClient(app) as client:
        response = client.post("/api/assistant/voice/event", json={"event_type": "voice:recording_started"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_transcribe_route_returns_error_when_stt_unavailable() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/assistant/transcribe",
            files={"file": ("sample.webm", io.BytesIO(b"fake audio"), "audio/webm")},
        )

    assert response.status_code in (400, 500, 503)


def test_identity_state_route_returns_defaults() -> None:
    with TestClient(app) as client:
        response = client.get("/api/assistant/identity")

    assert response.status_code == 200
    payload = response.json()
    profile_ids = {profile["id"] for profile in payload["profiles"]}
    assert {"zach", "aleena"}.issubset(profile_ids)
    assert payload["nickname_policy"]["aleena_mama_enabled"] is True


def test_memory_route_crud_cycle() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/assistant/memory",
            json={
                "scope": "household",
                "category": "routine",
                "source": "explicit",
                "key": "quiet_hours",
                "value": "After 9 PM keep responses softer.",
                "confidence": 1.0,
                "sensitive": False,
            },
        )
        assert created.status_code == 200
        item = created.json()["item"]

        fetched = client.get("/api/assistant/memory")
        assert fetched.status_code == 200
        assert any(entry["id"] == item["id"] for entry in fetched.json()["items"])

        deleted = client.delete(f"/api/assistant/memory/{item['id']}")
        assert deleted.status_code == 200
