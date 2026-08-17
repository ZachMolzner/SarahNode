from __future__ import annotations

import asyncio
import ctypes
import platform
from ctypes import wintypes
from typing import Any, Mapping

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition
from app.agent.windows_display import enable_per_monitor_dpi_awareness


class PointerControlError(RuntimeError):
    pass


_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004


def _require_windows() -> Any:
    if platform.system() != "Windows":
        raise PointerControlError("Visual pointer control is currently implemented for Windows only")
    enable_per_monitor_dpi_awareness()
    return ctypes.windll.user32


def _virtual_desktop_bounds() -> tuple[int, int, int, int]:
    user32 = _require_windows()
    left = int(user32.GetSystemMetrics(_SM_XVIRTUALSCREEN))
    top = int(user32.GetSystemMetrics(_SM_YVIRTUALSCREEN))
    width = int(user32.GetSystemMetrics(_SM_CXVIRTUALSCREEN))
    height = int(user32.GetSystemMetrics(_SM_CYVIRTUALSCREEN))
    if width <= 0 or height <= 0:
        raise PointerControlError("Windows did not return valid virtual desktop bounds")
    return left, top, width, height


def _validated_point(arguments: Mapping[str, Any]) -> tuple[int, int]:
    try:
        x = int(round(float(arguments.get("x"))))
        y = int(round(float(arguments.get("y"))))
    except (TypeError, ValueError) as exc:
        raise ValueError("x and y integer screen coordinates are required") from exc

    left, top, width, height = _virtual_desktop_bounds()
    right = left + width - 1
    bottom = top + height - 1
    if x < left or x > right or y < top or y > bottom:
        raise ValueError(
            f"Pointer target ({x}, {y}) is outside the virtual desktop bounds "
            f"({left}, {top}) to ({right}, {bottom})"
        )
    return x, y


async def move_pointer_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    user32 = _require_windows()
    x, y = _validated_point(arguments)
    if not user32.SetCursorPos(x, y):
        raise PointerControlError("Windows did not move the pointer to the requested location")
    await asyncio.sleep(0.05)
    point = wintypes.POINT()
    actual_x, actual_y = x, y
    if user32.GetCursorPos(ctypes.byref(point)):
        actual_x, actual_y = int(point.x), int(point.y)
    return {
        "action": "pointer_moved",
        "x": actual_x,
        "y": actual_y,
    }


async def click_pointer_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    user32 = _require_windows()
    x, y = _validated_point(arguments)

    # Reposition immediately before the click so execution uses the frozen/freshly
    # revalidated target coordinate rather than wherever the user moved the pointer.
    if not user32.SetCursorPos(x, y):
        raise PointerControlError("Windows did not move the pointer to the confirmed click location")
    await asyncio.sleep(0.08)

    user32.mouse_event(_MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    await asyncio.sleep(0.04)
    user32.mouse_event(_MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return {
        "action": "left_clicked",
        "x": x,
        "y": y,
        "click_count": 1,
        "button": "left",
    }


def pointer_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="move_pointer",
            description=(
                "Internal Phase 5C visual-control tool. Move the Windows pointer to an already "
                "validated visual target. Use only through the deterministic visual interaction flow."
            ),
            handler=move_pointer_handler,
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.SCREEN_POINTER}),
            risk=RiskLevel.LOW,
            requires_confirmation=False,
            model_visible=False,
        ),
        ToolDefinition(
            name="click_pointer",
            description=(
                "Internal Phase 5C visual-control tool. Perform one left click at an already "
                "validated visual target. Requires explicit user confirmation. No double-click, "
                "right-click, dragging, scrolling, or keyboard input."
            ),
            handler=click_pointer_handler,
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
                "required": ["x", "y"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.SCREEN_CLICK}),
            risk=RiskLevel.MEDIUM,
            requires_confirmation=True,
            model_visible=False,
        ),
    ]
