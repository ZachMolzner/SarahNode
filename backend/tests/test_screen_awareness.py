from __future__ import annotations

import asyncio
import json
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
    assert screen.is_screen_awareness_request("Find the Save button")
    assert screen.is_screen_awareness_request("Which button should I click to continue?")
    assert screen.is_screen_awareness_request("Look at this error and tell me what to do")

    assert not screen.is_screen_awareness_request("What is my screen resolution?")
    assert not screen.is_screen_awareness_request("Open Calculator")
    assert not screen.is_screen_awareness_request("Tell me about OLED screens")


def test_screen_reasoning_modes_are_deterministic() -> None:
    assert screen.classify_screen_reasoning_mode("What is on my screen?") is screen.ScreenReasoningMode.DESCRIBE
    assert screen.classify_screen_reasoning_mode("Read the text on my screen") is screen.ScreenReasoningMode.READ
    assert screen.classify_screen_reasoning_mode("What error is on my screen and how do I fix it?") is screen.ScreenReasoningMode.DIAGNOSE
    assert screen.classify_screen_reasoning_mode("Find the Save button") is screen.ScreenReasoningMode.LOCATE
    assert screen.classify_screen_reasoning_mode("Which button should I click to continue?") is screen.ScreenReasoningMode.PLAN


def test_screen_read_has_its_own_permission_scope() -> None:
    policy = default_policy()
    assert PermissionScope.SCREEN_READ in policy.granted_scopes
    assert PermissionScope.DESKTOP_CONTROL not in policy.granted_scopes
    assert PermissionScope.SYSTEM_CONTROL not in policy.granted_scopes


def test_in_memory_capture_resizes_without_writing_files(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_image = Image.new("RGB", (4000, 2000), "white")
    monkeypatch.setattr(screen.ImageGrab, "grab", lambda **_kwargs: fake_image.copy())
    monkeypatch.setattr(screen.ScreenAwarenessService, "_cursor_monitor_bbox", staticmethod(lambda: (100, 200, 4100, 2200)))
    monkeypatch.setattr(settings, "screen_capture_max_dimension", 1000)
    monkeypatch.setattr(settings, "screen_capture_jpeg_quality", 80)

    encoded = screen.ScreenAwarenessService._encode_frame()
    data_url, source_width, source_height, sent_width, sent_height, left, top, width, height = encoded

    assert data_url.startswith("data:image/jpeg;base64,")
    assert (source_width, source_height) == (4000, 2000)
    assert (sent_width, sent_height) == (1000, 500)
    assert (left, top, width, height) == (100, 200, 4000, 2000)


def _fake_frame() -> screen._CapturedFrame:
    return screen._CapturedFrame(
        data_url="data:image/jpeg;base64,ZmFrZQ==",
        source_width=1920,
        source_height=1080,
        sent_width=1920,
        sent_height=1080,
        capture_left=0,
        capture_top=0,
        capture_width=1920,
        capture_height=1080,
        sarah_hidden_for_capture=True,
    )


def test_visual_description_sends_image_to_local_vision_model(monkeypatch: pytest.MonkeyPatch) -> None:
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
        return _fake_frame()

    monkeypatch.setattr(service, "_capture", fake_capture)
    result = asyncio.run(service.analyze("What is on my screen?"))

    assert result.text == "A calculator window is visible."
    assert result.reasoning_mode == "describe"
    assert captured_request["model"] == settings.local_vision_model
    user_content = captured_request["messages"][1]["content"]
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_visual_plan_parses_targets_steps_and_caution(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "answer": "The Continue button is the appropriate visible next step.",
        "observations": ["A setup dialog is visible."],
        "recommended_steps": ["Review the selected options.", "Choose Continue if they are correct."],
        "targets": [
            {
                "label": "Continue",
                "role": "button",
                "visible_text": "Continue",
                "bbox": [720, 820, 930, 930],
                "confidence": 0.93,
            }
        ],
        "caution": "Continuing may apply the options shown in the installer.",
    }

    class FakeCompletions:
        async def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    service = screen.ScreenAwarenessService(default_policy())
    service.client = FakeClient()

    async def fake_capture() -> screen._CapturedFrame:
        return _fake_frame()

    monkeypatch.setattr(service, "_capture", fake_capture)
    result = asyncio.run(service.analyze("Which button should I click to continue?"))

    assert result.reasoning_mode == "plan"
    assert result.recommended_steps == (
        "Review the selected options.",
        "Choose Continue if they are correct.",
    )
    assert len(result.targets) == 1
    assert result.targets[0].label == "Continue"
    assert result.targets[0].bbox_normalized == (720, 820, 930, 930)
    assert result.targets[0].confidence == pytest.approx(0.93)
    assert "lower-right" in result.text
    assert "Suggested steps:" in result.text
    assert "Caution:" in result.text


def test_structured_reasoning_falls_back_to_raw_text(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCompletions:
        async def create(self, **_kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="I can see the error, but the button label is too small to read."))]
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    service = screen.ScreenAwarenessService(default_policy())
    service.client = FakeClient()

    async def fake_capture() -> screen._CapturedFrame:
        return _fake_frame()

    monkeypatch.setattr(service, "_capture", fake_capture)
    result = asyncio.run(service.analyze("Find the button I should press"))

    assert result.reasoning_mode == "locate"
    assert result.targets == ()
    assert "too small" in result.text


def test_invalid_target_bbox_is_not_trusted() -> None:
    targets = screen.ScreenAwarenessService._parse_targets(
        [{"label": "Save", "role": "button", "bbox": [900, 900, 100, 100], "confidence": 4.0}]
    )
    assert len(targets) == 1
    assert targets[0].bbox_normalized is None
    assert targets[0].confidence == 1.0


def test_screen_capture_refuses_when_scope_is_revoked() -> None:
    policy = default_policy()
    policy.revoke(PermissionScope.SCREEN_READ)
    service = screen.ScreenAwarenessService(policy)

    with pytest.raises(screen.ScreenAwarenessError):
        service._require_permission()
