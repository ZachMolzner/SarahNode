from __future__ import annotations

import base64
import io

from PIL import Image, ImageDraw

from app.services.screen_change_detection import compare_captured_frames


def _data_url(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def test_identical_frames_do_not_report_visible_change() -> None:
    image = Image.new("RGB", (800, 600), "white")
    result = compare_captured_frames(_data_url(image), _data_url(image.copy()))
    assert result.changed is False
    assert result.mean_difference < 3.0


def test_large_viewport_shift_reports_visible_change() -> None:
    before = Image.new("RGB", (800, 600), "white")
    after = Image.new("RGB", (800, 600), "white")
    draw_before = ImageDraw.Draw(before)
    draw_after = ImageDraw.Draw(after)
    draw_before.rectangle((80, 180, 720, 300), fill="black")
    draw_after.rectangle((80, 360, 720, 480), fill="black")

    result = compare_captured_frames(_data_url(before), _data_url(after))
    assert result.changed is True
    assert result.mean_difference >= 3.0
