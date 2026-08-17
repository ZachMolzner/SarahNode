from __future__ import annotations

import ctypes
import platform
from typing import Any, Mapping

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition


async def screen_info_handler(_arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if platform.system() != "Windows":
        return {
            "platform": platform.system(),
            "supported": False,
            "reason": "Phase 5 screen metadata is currently optimized for Windows",
        }

    user32 = ctypes.windll.user32
    return {
        "platform": "Windows",
        "supported": True,
        "monitor_count": int(user32.GetSystemMetrics(80)),  # SM_CMONITORS
        "virtual_left": int(user32.GetSystemMetrics(76)),   # SM_XVIRTUALSCREEN
        "virtual_top": int(user32.GetSystemMetrics(77)),    # SM_YVIRTUALSCREEN
        "virtual_width": int(user32.GetSystemMetrics(78)),  # SM_CXVIRTUALSCREEN
        "virtual_height": int(user32.GetSystemMetrics(79)), # SM_CYVIRTUALSCREEN
        "capture_policy": "explicit_requests_only",
        "screenshot_persistence": "ephemeral_in_memory",
    }


def screen_read_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="screen_info",
            description=(
                "Return read-only display metadata such as monitor count and virtual desktop dimensions. "
                "This does not capture or analyze screenshot pixels."
            ),
            handler=screen_info_handler,
            scopes=frozenset({PermissionScope.SCREEN_READ}),
            risk=RiskLevel.READ_ONLY,
        )
    ]
