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
_MOUSEEVENTF_WHEEL = 0x0800
_WHEEL_DELTA = 120
_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_MAX_TYPE_CHARS = 500
_MAX_SCROLL_STEPS = 5


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


def _require_windows() -> Any:
    if platform.system() != "Windows":
        raise PointerControlError("Visual input control is currently implemented for Windows only")
    enable_per_monitor_dpi_awareness()
    user32 = ctypes.windll.user32
    user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
    user32.mouse_event.restype = None
    return user32


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


def _validated_text(arguments: Mapping[str, Any]) -> str:
    value = arguments.get("text")
    if not isinstance(value, str):
        raise ValueError("Literal text is required")
    if not value:
        raise ValueError("Text cannot be empty")
    if len(value) > _MAX_TYPE_CHARS:
        raise ValueError(f"A single typing action is limited to {_MAX_TYPE_CHARS} characters")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Control characters, Enter, Tab, and newlines are not allowed in literal typing")
    return value


def _validated_scroll(arguments: Mapping[str, Any]) -> tuple[str, int]:
    direction = str(arguments.get("direction") or "").strip().lower()
    if direction not in {"up", "down"}:
        raise ValueError("Scroll direction must be 'up' or 'down'")
    try:
        steps = int(arguments.get("steps", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("Scroll steps must be an integer") from exc
    if steps < 1 or steps > _MAX_SCROLL_STEPS:
        raise ValueError(f"A single scroll action is limited to 1-{_MAX_SCROLL_STEPS} steps")
    return direction, steps


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


async def type_text_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    user32 = _require_windows()
    text = _validated_text(arguments)
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT

    utf16 = text.encode("utf-16-le")
    units = [int.from_bytes(utf16[index : index + 2], "little") for index in range(0, len(utf16), 2)]
    events: list[_INPUT] = []
    for unit in units:
        down = _INPUT(type=_INPUT_KEYBOARD)
        down.ki = _KEYBDINPUT(0, unit, _KEYEVENTF_UNICODE, 0, 0)
        up = _INPUT(type=_INPUT_KEYBOARD)
        up.ki = _KEYBDINPUT(0, unit, _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP, 0, 0)
        events.extend((down, up))

    array_type = _INPUT * len(events)
    event_array = array_type(*events)
    sent = int(user32.SendInput(len(events), event_array, ctypes.sizeof(_INPUT)))
    if sent != len(events):
        raise PointerControlError(f"Windows accepted only {sent} of {len(events)} literal typing events")
    await asyncio.sleep(0.05)
    return {
        "action": "literal_text_typed",
        "character_count": len(text),
        "special_keys": False,
        "clipboard_used": False,
    }


async def scroll_pointer_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    user32 = _require_windows()
    direction, steps = _validated_scroll(arguments)
    delta = _WHEEL_DELTA if direction == "up" else -_WHEEL_DELTA
    encoded_delta = ctypes.c_uint32(delta).value
    for _ in range(steps):
        user32.mouse_event(_MOUSEEVENTF_WHEEL, 0, 0, encoded_delta, 0)
        await asyncio.sleep(0.04)
    return {
        "action": "wheel_scrolled",
        "direction": direction,
        "steps": steps,
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
                "validated visual target. Requires explicit user confirmation."
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
        ToolDefinition(
            name="type_text",
            description=(
                "Internal Phase 5C.2 tool. Type only the exact literal Unicode text supplied by the "
                "deterministic visual interaction flow. No Enter, Tab, shortcuts, control characters, "
                "clipboard paste, or model-selected keystrokes."
            ),
            handler=type_text_handler,
            parameters={
                "type": "object",
                "properties": {"text": {"type": "string", "minLength": 1, "maxLength": _MAX_TYPE_CHARS}},
                "required": ["text"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.SCREEN_TYPE}),
            risk=RiskLevel.MEDIUM,
            requires_confirmation=True,
            model_visible=False,
        ),
        ToolDefinition(
            name="scroll_pointer",
            description=(
                "Internal Phase 5C.2 tool. Scroll the current Windows UI up or down by a bounded "
                "number of wheel steps. No horizontal scroll or unbounded repetition."
            ),
            handler=scroll_pointer_handler,
            parameters={
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down"]},
                    "steps": {"type": "integer", "minimum": 1, "maximum": _MAX_SCROLL_STEPS},
                },
                "required": ["direction", "steps"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.SCREEN_SCROLL}),
            risk=RiskLevel.LOW,
            requires_confirmation=False,
            model_visible=False,
        ),
    ]
