from __future__ import annotations

import base64
import io
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageStat

from app.services.screen_awareness import ScreenAwarenessService


@dataclass(frozen=True, slots=True)
class ScreenChangeResult:
    changed: bool
    mean_difference: float


def _frame_thumbnail(data_url: str) -> Image.Image:
    _prefix, separator, encoded = data_url.partition(",")
    if not separator or not encoded:
        raise ValueError("Invalid captured screen data URL")
    raw = base64.b64decode(encoded)
    with Image.open(io.BytesIO(raw)) as image:
        gray = image.convert("L")
        width, height = gray.size
        # Ignore the top portion of the frame where browser chrome, clocks, tabs,
        # and other non-scroll content can add noise. The lower viewport is a better
        # signal for whether visible page/content position changed.
        crop_top = min(height - 1, max(0, int(round(height * 0.14))))
        viewport = gray.crop((0, crop_top, width, height))
        return viewport.resize((160, 90), Image.Resampling.BILINEAR).copy()


def compare_captured_frames(before_data_url: str, after_data_url: str) -> ScreenChangeResult:
    before = _frame_thumbnail(before_data_url)
    after = _frame_thumbnail(after_data_url)
    difference = ImageChops.difference(before, after)
    mean_difference = float(ImageStat.Stat(difference).mean[0])
    # JPEG capture noise and tiny blinking UI changes usually stay below this value;
    # ordinary page scrolling changes a substantial portion of the viewport.
    return ScreenChangeResult(changed=mean_difference >= 3.0, mean_difference=mean_difference)


async def verify_visible_screen_change(
    screen: ScreenAwarenessService,
    before_data_url: str,
) -> ScreenChangeResult:
    after = await screen._capture()
    return compare_captured_frames(before_data_url, after.data_url)
