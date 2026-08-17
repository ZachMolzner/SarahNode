from __future__ import annotations

import ctypes
import platform
from ctypes import wintypes
from typing import Any, Mapping

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition
from app.agent.desktop_action_tools import _app_executable, _matching_pids


_SW_RESTORE = 9
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_SHOWWINDOW = 0x0040
_HWND_TOP = 0


def _configure_win32() -> tuple[Any, Any]:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.SetActiveWindow.argtypes = [wintypes.HWND]
    user32.SetActiveWindow.restype = wintypes.HWND
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.SetFocus.restype = wintypes.HWND
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL

    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    return user32, kernel32


def _window_pid(user32: Any, hwnd: int | None) -> int | None:
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value) if pid.value else None


def _find_visible_window(user32: Any, pids: set[int]) -> tuple[int | None, str]:
    target_hwnd: int | None = None
    target_title = ""
    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_proc(hwnd: int, _lparam: int) -> bool:
        nonlocal target_hwnd, target_title
        if not user32.IsWindowVisible(hwnd):
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) not in pids:
            return True

        length = int(user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()
        if not title:
            return True

        target_hwnd = int(hwnd)
        target_title = title
        return False

    user32.EnumWindows(enum_proc_type(enum_proc), 0)
    return target_hwnd, target_title


def _foreground_belongs_to(user32: Any, pids: set[int]) -> bool:
    hwnd = user32.GetForegroundWindow()
    pid = _window_pid(user32, int(hwnd) if hwnd else None)
    return pid in pids if pid is not None else False


def _attach_pair(user32: Any, first: int, second: int, attached: list[tuple[int, int]]) -> None:
    if not first or not second or first == second:
        return
    if user32.AttachThreadInput(first, second, True):
        attached.append((first, second))


def _focus_windows_process(executable: str) -> dict[str, Any]:
    """Bring an existing Windows app window to the foreground as reliably as Win32 allows.

    Windows restricts foreground activation to prevent background focus stealing. For
    an explicit user-requested switch, Sarah first tries the normal foreground API.
    If Windows rejects that request, Sarah temporarily joins the relevant input queues,
    raises/restores the target window, requests activation again, and verifies the
    actual foreground process before reporting success.
    """
    if platform.system() != "Windows":
        return {"supported": False, "focused": False, "raised": False, "reason": "Windows-only focus support"}

    pids = _matching_pids(executable)
    if not pids:
        return {"supported": True, "focused": False, "raised": False, "reason": "App is not running"}

    user32, kernel32 = _configure_win32()
    target_hwnd, target_title = _find_visible_window(user32, pids)
    if not target_hwnd:
        return {
            "supported": True,
            "focused": False,
            "raised": False,
            "reason": "The app is running but no visible window was found",
            "process_count": len(pids),
        }

    hwnd = wintypes.HWND(target_hwnd)
    user32.ShowWindow(hwnd, _SW_RESTORE)
    user32.BringWindowToTop(hwnd)
    user32.SetWindowPos(
        hwnd,
        wintypes.HWND(_HWND_TOP),
        0,
        0,
        0,
        0,
        _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW,
    )

    # Fast path: this succeeds whenever Windows already considers Sarah's backend
    # eligible to perform the requested foreground transition.
    user32.SetForegroundWindow(hwnd)
    if _foreground_belongs_to(user32, pids):
        return {
            "supported": True,
            "focused": True,
            "raised": True,
            "title": target_title,
            "process_count": len(pids),
            "method": "set_foreground_window",
            "reason": None,
        }

    current_thread = int(kernel32.GetCurrentThreadId())
    target_pid = wintypes.DWORD()
    target_thread = int(user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid)))

    foreground_hwnd = user32.GetForegroundWindow()
    foreground_thread = 0
    if foreground_hwnd:
        foreground_pid = wintypes.DWORD()
        foreground_thread = int(
            user32.GetWindowThreadProcessId(foreground_hwnd, ctypes.byref(foreground_pid))
        )

    attached: list[tuple[int, int]] = []
    try:
        _attach_pair(user32, current_thread, foreground_thread, attached)
        _attach_pair(user32, current_thread, target_thread, attached)

        user32.ShowWindow(hwnd, _SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        user32.SetWindowPos(
            hwnd,
            wintypes.HWND(_HWND_TOP),
            0,
            0,
            0,
            0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW,
        )
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        for first, second in reversed(attached):
            user32.AttachThreadInput(first, second, False)

    focused = _foreground_belongs_to(user32, pids)
    return {
        "supported": True,
        "focused": focused,
        "raised": True,
        "title": target_title,
        "process_count": len(pids),
        "method": "attached_input_queues" if focused else "z_order_only",
        "reason": None if focused else "Windows raised the window but kept keyboard focus in the current app",
    }


async def focus_app_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    app = str(arguments.get("app", "")).strip()
    if not app:
        raise ValueError("app is required")

    executable = _app_executable(app)
    result = _focus_windows_process(executable)
    return {"app": app, "executable": executable, **result}


def hardened_focus_app_tool() -> ToolDefinition:
    return ToolDefinition(
        name="focus_app",
        description=(
            "Use only when the user explicitly asks Sarah to switch to or bring an already-running supported Windows app to the front. "
            "Restores the app, raises its visible window, and verifies whether Windows actually moved keyboard focus to it."
        ),
        handler=focus_app_handler,
        parameters={
            "type": "object",
            "properties": {"app": {"type": "string"}},
            "required": ["app"],
            "additionalProperties": False,
        },
        scopes=frozenset({PermissionScope.APPS_FOCUS}),
        risk=RiskLevel.LOW,
    )
