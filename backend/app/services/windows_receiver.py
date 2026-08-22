from __future__ import annotations

import ctypes
import platform
import threading
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


_SW_RESTORE = 9
_SWP_NOMOVE = 0x0002
_SWP_NOSIZE = 0x0001
_SWP_SHOWWINDOW = 0x0040
_HWND_TOP = 0
_GA_ROOT = 2
_IGNORED_RECEIVER_TITLES = {"program manager"}


@dataclass(frozen=True, slots=True)
class VerifiedReceiver:
    hwnd: int
    title: str
    source: str
    verified_at: datetime
    expires_at: datetime


_verified_receiver_lock = threading.Lock()
_verified_receiver: VerifiedReceiver | None = None


def remember_verified_receiver(
    hwnd: int,
    title: str,
    *,
    source: str = "visual_interaction",
    ttl_seconds: int = 180,
) -> VerifiedReceiver | None:
    """Remember one recently verified top-level receiver for a short continuation.

    This is deliberately ephemeral process memory. It lets a controlled keyboard request
    continue operating on a field/window that Sarah just revalidated visually even after
    the user returns to Sarah's chat box to type the next command. It is not persisted and
    never grants broad keyboard control.
    """
    global _verified_receiver
    hwnd = int(hwnd or 0)
    clean_title = str(title or "").strip()
    if hwnd <= 0 or not clean_title or clean_title.lower() in _IGNORED_RECEIVER_TITLES:
        return None

    now = datetime.now(timezone.utc)
    remembered = VerifiedReceiver(
        hwnd=hwnd,
        title=clean_title,
        source=str(source or "visual_interaction"),
        verified_at=now,
        expires_at=now + timedelta(seconds=max(30, int(ttl_seconds))),
    )
    with _verified_receiver_lock:
        _verified_receiver = remembered
    return remembered


def get_verified_receiver() -> VerifiedReceiver | None:
    global _verified_receiver
    with _verified_receiver_lock:
        remembered = _verified_receiver
        if remembered is None:
            return None
        if remembered.expires_at <= datetime.now(timezone.utc):
            _verified_receiver = None
            return None
        return remembered


def clear_verified_receiver() -> VerifiedReceiver | None:
    global _verified_receiver
    with _verified_receiver_lock:
        previous = _verified_receiver
        _verified_receiver = None
        return previous


def _configure_win32():
    if platform.system() != "Windows":
        return None, None
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Keep EnumWindows callback typing local to top_visible_window. ctypes can reject
    # a WINFUNCTYPE callback when the DLL function is globally declared as c_void_p.
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
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


def _window_title_with(user32, hwnd: int) -> str:
    if hwnd <= 0 or not user32.IsWindow(wintypes.HWND(hwnd)):
        return ""
    handle = wintypes.HWND(hwnd)
    length = int(user32.GetWindowTextLengthW(handle))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value.strip()


def _usable_receiver_title(title: str) -> bool:
    clean = str(title or "").strip()
    return bool(clean) and clean.lower() not in _IGNORED_RECEIVER_TITLES


def window_title(hwnd: int) -> str:
    user32, _kernel32 = _configure_win32()
    if user32 is None:
        return ""
    return _window_title_with(user32, hwnd)


def foreground_window() -> tuple[int, str] | None:
    user32, _kernel32 = _configure_win32()
    if user32 is None:
        return None
    hwnd = _as_int(user32.GetForegroundWindow())
    if hwnd <= 0:
        return None
    title = _window_title_with(user32, hwnd)
    if not _usable_receiver_title(title):
        return None
    return hwnd, title


def window_at_point(x: int, y: int, *, exclude_hwnd: int | None = None) -> tuple[int, str] | None:
    """Return the visible top-level application window at a physical screen point."""
    user32, _kernel32 = _configure_win32()
    if user32 is None:
        return None

    point = wintypes.POINT(int(x), int(y))
    child = user32.WindowFromPoint(point)
    child_int = _as_int(child)
    if child_int <= 0:
        return None

    root = user32.GetAncestor(child, _GA_ROOT)
    hwnd = _as_int(root) or child_int
    excluded = int(exclude_hwnd or 0)
    if hwnd <= 0 or hwnd == excluded:
        return None
    handle = wintypes.HWND(hwnd)
    if not user32.IsWindow(handle) or not user32.IsWindowVisible(handle):
        return None

    title = _window_title_with(user32, hwnd)
    if not _usable_receiver_title(title):
        return None
    return hwnd, title


def window_at_cursor(*, exclude_hwnd: int | None = None) -> tuple[int, str] | None:
    """Return the visible top-level application window under the current pointer."""
    user32, _kernel32 = _configure_win32()
    if user32 is None:
        return None

    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return None
    return window_at_point(int(point.x), int(point.y), exclude_hwnd=exclude_hwnd)


def top_visible_window(*, exclude_hwnd: int | None = None) -> tuple[int, str] | None:
    """Return the topmost usable visible titled top-level window in current z-order."""
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
        title = _window_title_with(user32, hwnd_int)
        if not _usable_receiver_title(title):
            return True
        found = (hwnd_int, title)
        return False

    callback = enum_proc_type(enum_proc)
    user32.EnumWindows(callback, 0)
    return found


def activate_window(hwnd: int) -> bool:
    """Explicitly activate a known visible top-level window and verify foreground."""
    user32, kernel32 = _configure_win32()
    if user32 is None or kernel32 is None or hwnd <= 0:
        return False

    target = wintypes.HWND(hwnd)
    if not user32.IsWindow(target) or not user32.IsWindowVisible(target):
        return False
    if not _usable_receiver_title(_window_title_with(user32, hwnd)):
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
