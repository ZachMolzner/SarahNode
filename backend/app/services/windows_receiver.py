from __future__ import annotations

import ctypes
import platform
from ctypes import wintypes


_GW_HWNDNEXT = 2
_SW_RESTORE = 9
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_SHOWWINDOW = 0x0040
_HWND_TOP = 0


def _configure_win32():
    if platform.system() != "Windows":
        return None, None
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
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

    kernel32.GetCurrentThreadId.argtypes = []
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    return user32, kernel32


def _as_int(hwnd) -> int:
    if hwnd is None:
        return 0
    value = getattr(hwnd, "value", hwnd)
    return int(value or 0)


def window_title(hwnd: int) -> str:
    user32, _kernel32 = _configure_win32()
    if user32 is None or hwnd <= 0 or not user32.IsWindow(wintypes.HWND(hwnd)):
        return ""
    handle = wintypes.HWND(hwnd)
    length = int(user32.GetWindowTextLengthW(handle))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value.strip()


def foreground_window() -> tuple[int, str] | None:
    user32, _kernel32 = _configure_win32()
    if user32 is None:
        return None
    hwnd = _as_int(user32.GetForegroundWindow())
    if hwnd <= 0:
        return None
    return hwnd, window_title(hwnd) or f"Window 0x{hwnd:X}"


def top_visible_window(*, exclude_hwnd: int | None = None) -> tuple[int, str] | None:
    """Return the topmost visible titled top-level window in current z-order.

    EnumWindows enumerates top-level windows in z-order. Sarah calls this only while
    her own window is hidden; exclude_hwnd is still accepted as a second guard.
    """
    user32, _kernel32 = _configure_win32()
    if user32 is None:
        return None

    excluded = int(exclude_hwnd or 0)
    found: tuple[int, str] | None = None
    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_proc(hwnd, _lparam) -> bool:
        nonlocal found
        hwnd_int = _as_int(hwnd)
        if hwnd_int <= 0 or hwnd_int == excluded:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        title = window_title(hwnd_int)
        if not title:
            return True
        found = (hwnd_int, title)
        return False

    callback = enum_proc_type(enum_proc)
    user32.EnumWindows(callback, 0)
    return found


def activate_window(hwnd: int) -> bool:
    """Explicitly activate a known visible top-level window and verify foreground.

    This is used only while Sarah is hidden and only for a window selected from the
    current visible z-order or revalidated pending Enter receiver.
    """
    user32, kernel32 = _configure_win32()
    if user32 is None or kernel32 is None or hwnd <= 0:
        return False

    target = wintypes.HWND(hwnd)
    if not user32.IsWindow(target) or not user32.IsWindowVisible(target):
        return False

    user32.ShowWindow(target, _SW_RESTORE)
    user32.BringWindowToTop(target)
    user32.SetWindowPos(
        target,
        wintypes.HWND(_HWND_TOP),
        0,
        0,
        0,
        0,
        _SWP_NOMOVE | _SWP_NOSIZE | _SWP_SHOWWINDOW,
    )
    user32.SetForegroundWindow(target)
    if _as_int(user32.GetForegroundWindow()) == hwnd:
        return True

    current_thread = int(kernel32.GetCurrentThreadId())
    target_pid = wintypes.DWORD()
    target_thread = int(user32.GetWindowThreadProcessId(target, ctypes.byref(target_pid)))

    foreground = user32.GetForegroundWindow()
    foreground_thread = 0
    if foreground:
        foreground_pid = wintypes.DWORD()
        foreground_thread = int(user32.GetWindowThreadProcessId(foreground, ctypes.byref(foreground_pid)))

    attached: list[tuple[int, int]] = []

    def attach(first: int, second: int) -> None:
        if first and second and first != second and user32.AttachThreadInput(first, second, True):
            attached.append((first, second))

    try:
        attach(current_thread, foreground_thread)
        attach(current_thread, target_thread)
        user32.ShowWindow(target, _SW_RESTORE)
        user32.BringWindowToTop(target)
        user32.SetForegroundWindow(target)
        user32.SetActiveWindow(target)
        user32.SetFocus(target)
    finally:
        for first, second in reversed(attached):
            user32.AttachThreadInput(first, second, False)

    return _as_int(user32.GetForegroundWindow()) == hwnd
