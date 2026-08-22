from __future__ import annotations

import asyncio
import ctypes
import platform
import re
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.agent.contracts import ToolInvocation, ToolResult
from app.agent.tool_registry import ToolRegistry
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.screen_awareness import ScreenAwarenessService
from app.services.screen_change_detection import compare_captured_frames


_KEY_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:press|hit)\s+"
    r"(enter|return|escape|esc|tab|backspace|arrow\s+up|up\s+arrow|arrow\s+down|down\s+arrow)\s*$",
    re.IGNORECASE,
)
_ENTER_CONFIRM_RE = re.compile(r"^(?:yes[,.]?\s*)?confirm\s+enter$", re.IGNORECASE)
_CANCEL_RE = re.compile(r"^(?:cancel(?:\s+enter)?|no|never\s*mind|nevermind|stop)$", re.IGNORECASE)

_KEY_ALIASES = {
    "enter": "enter",
    "return": "enter",
    "escape": "escape",
    "esc": "escape",
    "tab": "tab",
    "backspace": "backspace",
    "arrow up": "arrow_up",
    "up arrow": "arrow_up",
    "arrow down": "arrow_down",
    "down arrow": "arrow_down",
}
_DISPLAY_NAMES = {
    "enter": "Enter",
    "escape": "Escape",
    "tab": "Tab",
    "backspace": "Backspace",
    "arrow_up": "Arrow Up",
    "arrow_down": "Arrow Down",
}

_GW_HWNDNEXT = 2
_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080
_SW_RESTORE = 9
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_SHOWWINDOW = 0x0040
_HWND_TOP = 0


@dataclass(frozen=True, slots=True)
class KeyboardRequest:
    key: str


@dataclass(frozen=True, slots=True)
class WindowContext:
    hwnd: int
    title: str


@dataclass(frozen=True, slots=True)
class PendingEnter:
    hwnd: int
    title: str
    created_at: datetime
    expires_at: datetime


class PendingEnterStore:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl = timedelta(seconds=max(30, ttl_seconds))
        self._pending: dict[str, PendingEnter] = {}

    def stage(self, user_id: str, context: WindowContext) -> PendingEnter:
        now = datetime.now(timezone.utc)
        pending = PendingEnter(
            hwnd=context.hwnd,
            title=context.title,
            created_at=now,
            expires_at=now + self.ttl,
        )
        self._pending[user_id] = pending
        return pending

    def get(self, user_id: str) -> PendingEnter | None:
        pending = self._pending.get(user_id)
        if pending is None:
            return None
        if pending.expires_at <= datetime.now(timezone.utc):
            self._pending.pop(user_id, None)
            return None
        return pending

    def pop(self, user_id: str) -> PendingEnter | None:
        pending = self.get(user_id)
        self._pending.pop(user_id, None)
        return pending

    def cancel(self, user_id: str) -> PendingEnter | None:
        return self._pending.pop(user_id, None)


def parse_keyboard_request(text: str) -> KeyboardRequest | None:
    raw = text.strip()
    if not raw or raw.endswith("?"):
        return None
    match = _KEY_RE.match(raw)
    if not match:
        return None
    normalized = re.sub(r"\s+", " ", match.group(1).strip().lower())
    key = _KEY_ALIASES.get(normalized)
    return KeyboardRequest(key=key) if key else None


def is_enter_confirmation(text: str) -> bool:
    return bool(_ENTER_CONFIRM_RE.match(text.strip()))


def is_keyboard_cancellation(text: str) -> bool:
    return bool(_CANCEL_RE.match(text.strip()))


def _configure_receiver_win32():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetWindow.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
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


def _hwnd_int(value) -> int:
    if value is None:
        return 0
    raw = getattr(value, "value", value)
    return int(raw or 0)


def _window_context(user32, hwnd_value) -> WindowContext | None:
    hwnd = _hwnd_int(hwnd_value)
    if hwnd <= 0:
        return None
    length = int(user32.GetWindowTextLengthW(hwnd_value))
    if length <= 0:
        return None
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd_value, buffer, len(buffer))
    title = buffer.value.strip()
    return WindowContext(hwnd=hwnd, title=title) if title else None


def _foreground_window_context() -> WindowContext | None:
    if platform.system() != "Windows":
        return None
    user32, _kernel32 = _configure_receiver_win32()
    return _window_context(user32, user32.GetForegroundWindow())


def _next_visible_window_under(sarah_hwnd: int) -> WindowContext | None:
    if platform.system() != "Windows" or sarah_hwnd <= 0:
        return None
    user32, _kernel32 = _configure_receiver_win32()
    candidate = user32.GetWindow(wintypes.HWND(sarah_hwnd), _GW_HWNDNEXT)
    checked = 0
    while candidate and checked < 100:
        checked += 1
        if user32.IsWindowVisible(candidate) and not user32.IsIconic(candidate):
            ex_style = int(user32.GetWindowLongW(candidate, _GWL_EXSTYLE))
            if not (ex_style & _WS_EX_TOOLWINDOW):
                context = _window_context(user32, candidate)
                if context is not None and context.hwnd != sarah_hwnd:
                    return context
        candidate = user32.GetWindow(candidate, _GW_HWNDNEXT)
    return None


def _attach_pair(user32, first: int, second: int, attached: list[tuple[int, int]]) -> None:
    if not first or not second or first == second:
        return
    if user32.AttachThreadInput(first, second, True):
        attached.append((first, second))


def _activate_window(context: WindowContext) -> bool:
    if platform.system() != "Windows" or context.hwnd <= 0:
        return False
    user32, kernel32 = _configure_receiver_win32()
    hwnd = wintypes.HWND(context.hwnd)

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
    if _hwnd_int(user32.GetForegroundWindow()) == context.hwnd:
        return True

    current_thread = int(kernel32.GetCurrentThreadId())
    target_pid = wintypes.DWORD()
    target_thread = int(user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid)))
    foreground_hwnd = user32.GetForegroundWindow()
    foreground_thread = 0
    if foreground_hwnd:
        foreground_pid = wintypes.DWORD()
        foreground_thread = int(user32.GetWindowThreadProcessId(foreground_hwnd, ctypes.byref(foreground_pid)))

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

    return _hwnd_int(user32.GetForegroundWindow()) == context.hwnd


def _verification_text(before_data_url: str | None, after_data_url: str | None) -> str:
    if not before_data_url or not after_data_url:
        return "I could not capture a reliable before/after viewport for verification."
    try:
        change = compare_captured_frames(before_data_url, after_data_url)
    except Exception:
        return "I could not compare the before/after viewport reliably."
    if change.changed:
        return "The visible interface changed after the key press."
    return "No clear visible interface change was detected after the key press."


class KeyboardInteractionService:
    """Phase 5C.3 deterministic single-key control.

    Only six named keys are recognized. Enter is always staged and confirmed in this
    first version because it can submit, send, navigate, purchase, install, or otherwise
    commit an action depending on focus. The other five keys execute only once per
    explicit request. Raw virtual-key codes, modifiers, hotkeys, repeats, and arbitrary
    key names are never accepted from the user or language model.
    """

    def __init__(
        self,
        screen: ScreenAwarenessService,
        tools: ToolRegistry,
        *,
        context_provider: Callable[[], WindowContext | None] = _foreground_window_context,
        underlying_provider: Callable[[int], WindowContext | None] = _next_visible_window_under,
        activator: Callable[[WindowContext], bool] = _activate_window,
    ) -> None:
        self.screen = screen
        self.tools = tools
        self.context_provider = context_provider
        self.underlying_provider = underlying_provider
        self.activator = activator
        self.pending = PendingEnterStore(ttl_seconds=120)

    def has_pending(self, user_id: str) -> bool:
        return self.pending.get(user_id) is not None

    def cancel_pending(self, user_id: str) -> PendingEnter | None:
        return self.pending.cancel(user_id)

    def can_handle(self, message: ChatMessage) -> bool:
        if self.has_pending(message.user_id) and (
            is_enter_confirmation(message.content) or is_keyboard_cancellation(message.content)
        ):
            return True
        return parse_keyboard_request(message.content) is not None

    def _hide_sarah(self) -> int | None:
        hide = getattr(self.screen, "_hide_sarah_if_foreground", None)
        return hide() if callable(hide) else None

    def _restore_sarah(self, hwnd: int | None) -> None:
        restore = getattr(self.screen, "_restore_sarah_window", None)
        if callable(restore):
            restore(hwnd)

    async def _capture_data_url(self) -> str | None:
        capture = getattr(self.screen, "_capture", None)
        if not callable(capture):
            return None
        try:
            frame = await capture()
        except Exception:
            return None
        return getattr(frame, "data_url", None)

    def _resolve_receiver(self, hidden_sarah_hwnd: int | None) -> WindowContext | None:
        if hidden_sarah_hwnd is not None:
            context = self.underlying_provider(hidden_sarah_hwnd)
            if context is None or context.hwnd == hidden_sarah_hwnd:
                return None
            if not self.activator(context):
                return None
            fresh = self.context_provider()
            if fresh is None or fresh.hwnd != context.hwnd:
                return None
            return fresh
        return self.context_provider()

    async def _peek_underlying_context(self) -> WindowContext | None:
        hidden_hwnd: int | None = None
        try:
            hidden_hwnd = self._hide_sarah()
            if hidden_hwnd is not None:
                await asyncio.sleep(0.25)
            return self._resolve_receiver(hidden_hwnd)
        finally:
            self._restore_sarah(hidden_hwnd)

    async def _execute_safe_key(self, key: str) -> AssistantReply:
        hidden_hwnd: int | None = None
        context: WindowContext | None = None
        result: ToolResult | None = None
        before_data_url: str | None = None
        after_data_url: str | None = None
        try:
            hidden_hwnd = self._hide_sarah()
            if hidden_hwnd is not None:
                await asyncio.sleep(0.25)
            context = self._resolve_receiver(hidden_hwnd)
            if context is None:
                return AssistantReply(
                    text="I did not press the key because I could not safely activate and verify the window underneath Sarah.",
                    emotion="concerned",
                    should_speak=True,
                )
            before_data_url = await self._capture_data_url()
            result = await self.tools.invoke(
                ToolInvocation(
                    tool_name="press_safe_key",
                    arguments={"key": key},
                    requested_by="controlled_keyboard_coordinator",
                )
            )
            if result.ok:
                await asyncio.sleep(0.25)
                after_data_url = await self._capture_data_url()
        finally:
            self._restore_sarah(hidden_hwnd)

        if result is None or not result.ok:
            error = result.error if result is not None else "The keyboard controller did not return a result."
            return AssistantReply(
                text=f"I did not complete the key press: {error or 'Windows rejected the key press.'}",
                emotion="concerned",
                should_speak=True,
            )

        display = _DISPLAY_NAMES[key]
        target = context.title if context is not None else "the underlying window"
        verification = _verification_text(before_data_url, after_data_url)
        return AssistantReply(
            text=f'Pressed {display} once in "{target}". No modifiers or hotkeys were used. Verification: {verification}',
            emotion="calm",
            should_speak=True,
        )

    async def _execute_confirmed_enter(self, user_id: str, pending: PendingEnter) -> AssistantReply:
        hidden_hwnd: int | None = None
        fresh_context: WindowContext | None = None
        result: ToolResult | None = None
        before_data_url: str | None = None
        after_data_url: str | None = None
        try:
            hidden_hwnd = self._hide_sarah()
            if hidden_hwnd is not None:
                await asyncio.sleep(0.25)
            fresh_context = self._resolve_receiver(hidden_hwnd)
            if fresh_context is None or fresh_context.hwnd != pending.hwnd:
                self.pending.cancel(user_id)
                actual = fresh_context.title if fresh_context is not None else "no safely activated underlying window"
                return AssistantReply(
                    text=(
                        f'I did not press Enter because the receiving window changed or could not be re-activated. '
                        f'It was staged for "{pending.title}", but the current receiver is {actual!r}. '
                        "Please request Enter again from the current screen."
                    ),
                    emotion="concerned",
                    should_speak=True,
                )

            self.pending.cancel(user_id)
            before_data_url = await self._capture_data_url()
            result = await self.tools.invoke(
                ToolInvocation(
                    tool_name="press_enter",
                    arguments={},
                    requested_by="confirmed_keyboard_enter_coordinator",
                ),
                confirmed=True,
            )
            if result.ok:
                await asyncio.sleep(0.35)
                after_data_url = await self._capture_data_url()
        finally:
            self._restore_sarah(hidden_hwnd)

        if result is None or not result.ok:
            error = result.error if result is not None else "The Enter controller did not return a result."
            return AssistantReply(
                text=f"I did not complete the confirmed Enter press: {error or 'Windows rejected Enter.'}",
                emotion="concerned",
                should_speak=True,
            )

        target = fresh_context.title if fresh_context is not None else pending.title
        verification = _verification_text(before_data_url, after_data_url)
        return AssistantReply(
            text=f'Pressed Enter once in the freshly re-verified "{target}" window. Verification: {verification}',
            emotion="calm",
            should_speak=True,
        )

    async def handle(self, message: ChatMessage, *, other_system_change_pending: bool = False) -> AssistantReply | None:
        user_id = message.user_id
        pending = self.pending.get(user_id)

        if pending is not None and is_keyboard_cancellation(message.content):
            self.pending.cancel(user_id)
            return AssistantReply(
                text=f'Cancelled. I did not press Enter in "{pending.title}".',
                emotion="calm",
                should_speak=True,
            )

        if pending is not None and is_enter_confirmation(message.content):
            return await self._execute_confirmed_enter(user_id, pending)

        request = parse_keyboard_request(message.content)
        if request is None:
            return None

        if pending is not None:
            return AssistantReply(
                text=(
                    f'Enter is already staged for "{pending.title}". Reply "confirm enter" or "cancel" '
                    "before requesting another controlled key."
                ),
                emotion="concerned",
                should_speak=True,
            )

        if other_system_change_pending:
            return AssistantReply(
                text="You already have another pending system change. Confirm or cancel it before using controlled keyboard input.",
                emotion="concerned",
                should_speak=True,
            )

        if request.key == "enter":
            context = await self._peek_underlying_context()
            if context is None:
                return AssistantReply(
                    text="I did not stage Enter because I could not safely activate and verify which underlying window would receive it.",
                    emotion="concerned",
                    should_speak=True,
                )
            self.pending.stage(user_id, context)
            return AssistantReply(
                text=(
                    f'Enter is staged for "{context.title}", but I have not pressed it. Enter can submit, send, search, '
                    'navigate, purchase, install, or confirm an action depending on focus. Reply "confirm enter" within '
                    '2 minutes to re-activate and re-verify that same receiving window and press Enter once, or "cancel".'
                ),
                emotion="concerned",
                should_speak=True,
            )

        return await self._execute_safe_key(request.key)
