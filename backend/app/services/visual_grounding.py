from __future__ import annotations

import json
import re
from typing import Any

from app.services.screen_awareness import (
    ScreenAnalysisResult,
    ScreenAwarenessError,
    ScreenAwarenessService,
    VisualTarget,
)


_TARGET_LINE_RE = re.compile(r"TARGET\s*\|", re.IGNORECASE)


def _clean_model_text(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:text|json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_bbox(values: list[str]) -> tuple[int, int, int, int] | None:
    if len(values) != 4:
        return None
    try:
        coords = [int(round(float(value.strip()))) for value in values]
    except (TypeError, ValueError):
        return None
    left, top, right, bottom = [max(0, min(1000, value)) for value in coords]
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _parse_confidence(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, confidence))


def _target_from_json(raw: str) -> tuple[VisualTarget | None, bool] | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None

    found = bool(payload.get("found"))
    if not found:
        return None, False

    label = str(payload.get("label") or payload.get("visible_text") or "").strip()
    if not label:
        return None, True
    bbox_value = payload.get("bbox")
    if not isinstance(bbox_value, (list, tuple)):
        return None, True
    bbox = _parse_bbox([str(item) for item in bbox_value])
    confidence = _parse_confidence(payload.get("confidence"))
    if bbox is None or confidence is None:
        return None, True

    return (
        VisualTarget(
            label=label,
            role=str(payload.get("role") or "control").strip() or "control",
            visible_text=str(payload.get("visible_text") or label).strip(),
            bbox_normalized=bbox,
            confidence=confidence,
        ),
        True,
    )


def _target_from_line(raw: str) -> tuple[VisualTarget | None, bool] | None:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    line = next((item for item in lines if _TARGET_LINE_RE.search(item)), "")
    if not line:
        return None

    marker = _TARGET_LINE_RE.search(line)
    assert marker is not None
    line = "TARGET|" + line[marker.end() :]
    parts = [part.strip() for part in line.split("|")]
    if len(parts) < 2:
        return None

    status = parts[1].upper().replace(" ", "_")
    if status in {"NOT_FOUND", "NO", "FALSE", "MISSING"}:
        return None, False
    if status not in {"FOUND", "YES", "TRUE"}:
        return None
    if len(parts) < 10:
        return None, True

    label = parts[2]
    role = parts[3] or "control"
    visible_text = parts[4] or label
    bbox = _parse_bbox(parts[5:9])
    confidence = _parse_confidence(parts[9])
    if not label or bbox is None or confidence is None:
        return None, True

    return (
        VisualTarget(
            label=label,
            role=role,
            visible_text=visible_text,
            bbox_normalized=bbox,
            confidence=confidence,
        ),
        True,
    )


def parse_plain_grounding(raw: str) -> tuple[VisualTarget | None, bool]:
    """Parse one safe target from a plain Qwen vision response.

    Returns (target, model_claimed_found). A claimed target with malformed coordinates
    deliberately returns (None, True) so callers can distinguish grounding failure from
    a genuine not-visible result.
    """
    cleaned = _clean_model_text(raw)
    json_result = _target_from_json(cleaned)
    if json_result is not None:
        return json_result
    line_result = _target_from_line(cleaned)
    if line_result is not None:
        return line_result
    return None, False


def _grounding_prompt(target_query: str, *, retry: bool = False) -> str:
    emphasis = "This is a retry. Output only the required line. " if retry else ""
    return (
        f'{emphasis}Visually locate exactly one UI control matching "{target_query}" in the screenshot. '
        "Do not describe the page. Do not use markdown. "
        "If clearly visible, output exactly: "
        "TARGET|FOUND|label|role|visible_text|left|top|right|bottom|confidence. "
        "left,top,right,bottom must be numbers from 0 to 1000 relative to the screenshot and confidence must be 0 to 1. "
        "Replace any | character in text with /. "
        "If it is not clearly visible, output exactly: TARGET|NOT_FOUND."
    )


async def locate_control_with_plain_vision(
    screen: ScreenAwarenessService,
    target_query: str,
) -> ScreenAnalysisResult:
    """Ground one control without Ollama structured-output mode.

    Qwen3-VL has been reliable for natural screen reading on the target Windows host,
    while format/schema mode has intermittently returned empty content. This path keeps
    the screenshot and model local, requests a tiny plain-text protocol, then validates
    all coordinates before exposing a VisualTarget to the pointer controller.
    """
    frame = await screen._capture()
    raw = await screen._request_vision(
        frame,
        _grounding_prompt(target_query),
        max_tokens=180,
        structured=False,
    )
    target, claimed_found = parse_plain_grounding(raw)

    if target is None and claimed_found:
        retry_raw = await screen._request_vision(
            frame,
            _grounding_prompt(target_query, retry=True),
            max_tokens=140,
            structured=False,
        )
        target, claimed_found = parse_plain_grounding(retry_raw)
        raw = retry_raw

    if target is not None:
        text = f'I can identify "{target.visible_text or target.label}" as the requested visible control.'
        targets = (target,)
    elif claimed_found:
        text = (
            f'I can see a possible match for "{target_query}", but the target coordinates were not usable, '
            "so I will not move the pointer."
        )
        targets = ()
    else:
        cleaned = _clean_model_text(raw)
        if cleaned.upper().startswith("TARGET|NOT_FOUND"):
            text = f'I can see the screen, but I cannot confidently find "{target_query}" on it.'
        else:
            text = (
                f'I can see the screen, but I could not get reliable grounding data for "{target_query}". '
                f"Vision response: {cleaned[:240]}" if cleaned else
                f'I can see the screen, but the vision model returned no usable grounding data for "{target_query}".'
            )
        targets = ()

    return ScreenAnalysisResult(
        text=text,
        model="plain-vision-grounding",
        reasoning_mode="locate",
        source_width=frame.source_width,
        source_height=frame.source_height,
        sent_width=frame.sent_width,
        sent_height=frame.sent_height,
        capture_left=frame.capture_left,
        capture_top=frame.capture_top,
        capture_width=frame.capture_width,
        capture_height=frame.capture_height,
        sarah_hidden_for_capture=frame.sarah_hidden_for_capture,
        targets=targets,
        recommended_steps=(),
        caution=None,
    )
