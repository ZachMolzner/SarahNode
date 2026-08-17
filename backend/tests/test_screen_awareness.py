from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from PIL import Image

import app.services.screen_awareness as screen
from app.agent.contracts import PermissionScope
from app.agent.permissions import default_policy
from app.config.settings import settings


def test_screen_request_routing_is_explicit() -> None:
    assert screen.is_screen_awareness_request("What is on my screen?")
    assert screen.is_screen_awareness_request("Look at my screen and tell me what error you see")
    assert screen.is_screen_awareness_request("What am I looking at?")
    assert screen.is_screen_awareness_request("Can you read the text on the screen?")

    assert not screen.is_screen_awareness_request("What is my screen resolution?")
    assert not screen.is_screen_awareness_request("Open Calculator")
    assert not screen.is_screen_awareness_request("Tell me about OLED screens")


def test_screen_read_has_its_own_permission_scope() -> None:
    policy = default_policy()
    assert PermissionScope.SCREEN_READ in policy.granted_scopes
    assert PermissionScope.DESKTOP_CONTROL not in policy.granted_scopes
    assert PermissionScope.SYSTEM_CONTROL not in policy.granted_scopes


def test_in_memory_capture_resizes_without_writing_files(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_image = Image.new("RGB", (4000, 2000), "white")
    monkeypatch.setattr(screen.ImageGrab, "grab", lambda **_kwargs: fake_image.copy())
    monkeypatch.setattr(screen.ScreenAwarenessService, "_cursor_monitor_bbox", staticmethod(lambda: (0, 0, 4000, 2000)))
    monkeypatch.setattr(settings, "screen_capture_max_dimension", 1000)
    monkeypatch.setattr(settings, "screen_capture_jpeg_quality", 80)

    data_url, source_width, source_height, sent_width, sent_height = screen.ScreenAwarenessService._encode_frame()

    assert data_url.startswith("data:image/jpeg;base64,")
    assert (source_width, source_height) == (4000, 2000)
    assert (sent_width, sent_height) == (1000, 500)


def test_visual_analysis_sends_image_to_local_vision_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_request: dict = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured_request.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="A calculator window is visible."))]
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    service = screen.ScreenAwarenessService(default_policy())
    service.client = FakeClient()

    async def fake_capture() -> screen._CapturedFrame:
        return screen._CapturedFrame(
            data_url="data:image/jpeg;base64,ZmFrZQ==",
            source_width=1920,
            source_height=1080,
            sent_width=1920,
            sent_height=1080,
            sarah_hidden_for_capture=True,
        )

    monkeypatch.setattr(service, "_capture", fake_capture)
    result = asyncio.run(service.analyze("What is on my screen?"))

    assert result.text == "A calculator window is visible."
    assert captured_request["model"] == settings.local_vision_model
    user_content = captured_request["messages"][1]["content"]
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_screen_capture_refuses_when_scope_is_revoked() -> None:
    policy = default_policy()
    policy.revoke(PermissionScope.SCREEN_READ)
    service = screen.ScreenAwarenessService(policy)

    with pytest.raises(screen.ScreenAwarenessError):
        service._require_permission()
