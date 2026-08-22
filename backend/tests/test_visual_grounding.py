from __future__ import annotations

import asyncio

import pytest

from app.agent.permissions import default_policy
from app.services.screen_awareness import ScreenAwarenessService, _CapturedFrame
from app.services.visual_grounding import locate_control_with_plain_vision, parse_plain_grounding


def _frame() -> _CapturedFrame:
    return _CapturedFrame(
        data_url="data:image/jpeg;base64,ZmFrZQ==",
        source_width=1920,
        source_height=1080,
        sent_width=1920,
        sent_height=1080,
        capture_left=100,
        capture_top=50,
        capture_width=1920,
        capture_height=1080,
        sarah_hidden_for_capture=True,
    )


def test_plain_grounding_line_parses_target() -> None:
    target, claimed_found = parse_plain_grounding(
        "TARGET|FOUND|Search the web|textbox|Search the web|240|120|760|210|0.94"
    )
    assert claimed_found is True
    assert target is not None
    assert target.label == "Search the web"
    assert target.role == "textbox"
    assert target.bbox_normalized == (240, 120, 760, 210)
    assert target.confidence == pytest.approx(0.94)


def test_plain_grounding_json_is_tolerated_without_schema_mode() -> None:
    target, claimed_found = parse_plain_grounding(
        '{"found":true,"label":"Not now","role":"button","visible_text":"Not now",'
        '"bbox":[700,100,900,200],"confidence":0.91}'
    )
    assert claimed_found is True
    assert target is not None
    assert target.label == "Not now"
    assert target.bbox_normalized == (700, 100, 900, 200)


def test_plain_grounding_rejects_malformed_claimed_coordinates() -> None:
    target, claimed_found = parse_plain_grounding(
        "TARGET|FOUND|Search the web|textbox|Search the web|900|200|100|100|0.99"
    )
    assert claimed_found is True
    assert target is None


def test_plain_grounding_not_found_is_not_a_target() -> None:
    target, claimed_found = parse_plain_grounding("TARGET|NOT_FOUND")
    assert claimed_found is False
    assert target is None


def test_locator_uses_plain_vision_without_structured_format(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ScreenAwarenessService(default_policy())
    calls: list[dict] = []

    async def fake_capture() -> _CapturedFrame:
        return _frame()

    async def fake_request(
        frame: _CapturedFrame,
        user_text: str,
        *,
        max_tokens: int,
        structured: bool = False,
        **_kwargs,
    ) -> str:
        calls.append(
            {
                "frame": frame,
                "user_text": user_text,
                "max_tokens": max_tokens,
                "structured": structured,
            }
        )
        return "TARGET|FOUND|Search the web|textbox|Search the web|250|100|750|190|0.96"

    monkeypatch.setattr(service, "_capture", fake_capture)
    monkeypatch.setattr(service, "_request_vision", fake_request)

    result = asyncio.run(locate_control_with_plain_vision(service, "Search the web"))

    assert len(calls) == 1
    assert calls[0]["structured"] is False
    assert "format" not in calls[0]
    assert len(result.targets) == 1
    assert result.targets[0].label == "Search the web"
    assert result.targets[0].bbox_normalized == (250, 100, 750, 190)
    assert result.capture_left == 100
    assert result.capture_top == 50


def test_locator_retries_malformed_found_target_without_moving(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ScreenAwarenessService(default_policy())
    responses = [
        "TARGET|FOUND|Search the web|textbox|Search the web|900|200|100|100|0.99",
        "TARGET|FOUND|Search the web|textbox|Search the web|260|110|740|200|0.95",
    ]

    async def fake_capture() -> _CapturedFrame:
        return _frame()

    async def fake_request(*_args, **_kwargs) -> str:
        return responses.pop(0)

    monkeypatch.setattr(service, "_capture", fake_capture)
    monkeypatch.setattr(service, "_request_vision", fake_request)

    result = asyncio.run(locate_control_with_plain_vision(service, "Search the web"))

    assert not responses
    assert len(result.targets) == 1
    assert result.targets[0].bbox_normalized == (260, 110, 740, 200)
