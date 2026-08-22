from __future__ import annotations

import asyncio
import json

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


def test_visual_description_uses_native_ollama_without_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_body: dict = {}
    service = screen.ScreenAwarenessService(default_policy())

    async def fake_capture() -> screen._CapturedFrame:
        return _fake_frame()

    async def fake_post(body: dict) -> dict:
        captured_body.update(body)
        return {"message": {"role": "assistant", "content": "A calculator window is visible."}}

    monkeypatch.setattr(service, "_capture", fake_capture)
    monkeypatch.setattr(service, "_post_ollama_chat", fake_post)

    result = asyncio.run(service.analyze("What is on my screen?"))

    assert result.text == "A calculator window is visible."
    assert result.reasoning_mode == "describe"
    assert captured_body["model"] == settings.local_vision_model
    assert captured_body["stream"] is False
    assert captured_body["think"] is False
    assert captured_body["keep_alive"] == "10m"
    assert captured_body["messages"][1]["images"] == ["ZmFrZQ=="]
    assert "format" not in captured_body


def test_visual_plan_uses_json_schema_and_parses_targets(monkeypatch: pytest.MonkeyPatch) -> None:
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
    captured_body: dict = {}
    service = screen.ScreenAwarenessService(default_policy())

    async def fake_capture() -> screen._CapturedFrame:
        return _fake_frame()

    async def fake_post(body: dict) -> dict:
        captured_body.update(body)
        return {"message": {"role": "assistant", "content": json.dumps(payload)}}

    monkeypatch.setattr(service, "_capture", fake_capture)
    monkeypatch.setattr(service, "_post_ollama_chat", fake_post)

    result = asyncio.run(service.analyze("Which button should I click to continue?"))

    assert isinstance(captured_body["format"], dict)
    assert captured_body["think"] is False
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


def test_empty_rich_vision_response_retries_once_with_plain_final_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    service = screen.ScreenAwarenessService(default_policy())

    async def fake_capture() -> screen._CapturedFrame:
        return _fake_frame()

    async def fake_post(body: dict) -> dict:
        calls.append(body)
        if len(calls) == 1:
            return {"message": {"role": "assistant", "content": "", "thinking": "hidden reasoning"}}
        return {"message": {"role": "assistant", "content": "The visible error says the connection failed."}}

    monkeypatch.setattr(service, "_capture", fake_capture)
    monkeypatch.setattr(service, "_post_ollama_chat", fake_post)

    result = asyncio.run(service.analyze("What error is on my screen and how do I fix it?"))

    assert len(calls) == 2
    assert "format" in calls[0]
    assert "format" not in calls[1]
    assert calls[0]["think"] is False
    assert calls[1]["think"] is False
    assert "connection failed" in result.text


def test_empty_locator_response_retries_with_compact_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    locator_payload = {
        "found": True,
        "label": "Search the web",
        "role": "textbox",
        "visible_text": "Search the web",
        "bbox": [250, 120, 750, 220],
        "confidence": 0.96,
        "answer": "The search box is visible near the upper center.",
    }
    service = screen.ScreenAwarenessService(default_policy())

    async def fake_capture() -> screen._CapturedFrame:
        return _fake_frame()

    async def fake_post(body: dict) -> dict:
        calls.append(body)
        if len(calls) == 1:
            return {"message": {"role": "assistant", "content": "", "thinking": "hidden reasoning"}}
        return {"message": {"role": "assistant", "content": json.dumps(locator_payload)}}

    monkeypatch.setattr(service, "_capture", fake_capture)
    monkeypatch.setattr(service, "_post_ollama_chat", fake_post)

    result = asyncio.run(service.analyze('Find the button, field, link, tab, checkbox, menu item, icon, or other visible UI control labeled "Search the web" on my screen.'))

    assert len(calls) == 2
    assert "format" in calls[0]
    assert "format" in calls[1]
    assert "found" in calls[0]["format"]["properties"]
    assert "targets" not in calls[0]["format"]["properties"]
    assert calls[0]["options"]["temperature"] == 0.0
    assert calls[1]["options"]["temperature"] == 0.0
    assert result.reasoning_mode == "locate"
    assert len(result.targets) == 1
    assert result.targets[0].label == "Search the web"
    assert result.targets[0].bbox_normalized == (250, 120, 750, 220)
    assert result.targets[0].confidence == pytest.approx(0.96)
    assert "upper center" in result.text


def test_structured_reasoning_falls_back_to_raw_text(monkeypatch: pytest.MonkeyPatch) -> None:
    service = screen.ScreenAwarenessService(default_policy())

    async def fake_capture() -> screen._CapturedFrame:
        return _fake_frame()

    async def fake_post(_body: dict) -> dict:
        return {"message": {"role": "assistant", "content": "I can see the error, but the button label is too small to read."}}

    monkeypatch.setattr(service, "_capture", fake_capture)
    monkeypatch.setattr(service, "_post_ollama_chat", fake_post)
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
