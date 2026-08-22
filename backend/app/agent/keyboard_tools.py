from __future__ import annotations

import asyncio
import ctypes
import platform
from ctypes import wintypes
from typing import Any, Mapping

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition
from app.agent.windows_display import enable_per_monitor_dpi_awareness


class KeyboardControlError(RuntimeError):
    pass


_INPUT_KEYBOARD = 1
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002

_VK_BACK = 0x08
_VK_TAB = 0x09
_VK_RETURN = 0x0D
_VK_ESCAPE = 0x1B
_VK_UP = 0x26
_VK_DOWN = 0x28

_SAFE_KEYS: dict[str, tuple[int, bool]] = {
    "escape": (_VK_ESCAPE, False),
    "tab": (_VK_TAB, False),
    "backspace": (_VK_BACK, False),
    "arrow_up": (_VK_UP, True),
    "arrow_down": (_VK_DOWN, True),
}


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
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
        ("ki", _KEYBDINPUT),
        ("mi", _MOUSEINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


def _require_windows() -> Any:
    if platform.system() != "Windows":
        raise KeyboardControlError("Controlled keyboard input is currently implemented for Windows only")
    enable_per_monitor_dpi_awareness()
    user32 = ctypes.windll.user32
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    return user32


def _send_one_key(vk: int, *, extended: bool = False) -> None:
    user32 = _require_windows()
    base_flags = _KEYEVENTF_EXTENDEDKEY if extended else 0

    down = _INPUT(type=_INPUT_KEYBOARD)
    down.ki = _KEYBDINPUT(vk, 0, base_flags, 0, 0)
    up = _INPUT(type=_INPUT_KEYBOARD)
    up.ki = _KEYBDINPUT(vk, 0, base_flags | _KEYEVENTF_KEYUP, 0, 0)

    events = (_INPUT * 2)(down, up)
    sent = int(user32.SendInput(2, events, ctypes.sizeof(_INPUT)))
    if sent != 2:
        raise KeyboardControlError(f"Windows accepted only {sent} of 2 controlled key events")


def _validated_safe_key(arguments: Mapping[str, Any]) -> tuple[str, int, bool]:
    key = str(arguments.get("key") or "").strip().lower()
    if key not in _SAFE_KEYS:
        raise ValueError("Only Escape, Tab, Backspace, Arrow Up, and Arrow Down are allowed by this tool")
    vk, extended = _SAFE_KEYS[key]
    return key, vk, extended


async def press_safe_key_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    key, vk, extended = _validated_safe_key(arguments)
    _send_one_key(vk, extended=extended)
    await asyncio.sleep(0.05)
    return {
        "action": "controlled_key_pressed",
        "key": key,
        "press_count": 1,
        "modifiers": [],
    }


async def press_enter_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    if arguments:
        raise ValueError("Enter does not accept key modifiers, repeat counts, or other arguments")
    _send_one_key(_VK_RETURN)
    await asyncio.sleep(0.05)
    return {
        "action": "confirmed_enter_pressed",
        "key": "enter",
        "press_count": 1,
        "modifiers": [],
    }


def keyboard_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="press_safe_key",
            description=(
                "Internal Phase 5C.3 tool. Press exactly one allowlisted navigation/edit key: "
                "Escape, Tab, Backspace, Arrow Up, or Arrow Down. No modifiers, repeats, hotkeys, "
                "text entry, function keys, or arbitrary virtual-key codes."
            ),
            handler=press_safe_key_handler,
            parameters={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "enum": ["escape", "tab", "backspace", "arrow_up", "arrow_down"],
                    }
                },
                "required": ["key"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.SCREEN_KEYS}),
            risk=RiskLevel.LOW,
            requires_confirmation=False,
            model_visible=False,
        ),
        ToolDefinition(
            name="press_enter",
            description=(
                "Internal Phase 5C.3 tool. Press Enter exactly once after the deterministic keyboard "
                "coordinator has staged the receiving window and obtained explicit user confirmation. "
                "No modifiers, repeats, or combined key sequences."
            ),
            handler=press_enter_handler,
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.SCREEN_KEYS}),
            risk=RiskLevel.MEDIUM,
            requires_confirmation=True,
            model_visible=False,
        ),
    ]
