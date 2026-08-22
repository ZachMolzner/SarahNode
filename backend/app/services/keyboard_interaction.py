from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.agent.contracts import ToolInvocation, ToolResult
from app.agent.tool_registry import ToolRegistry
from app.memory.secret_guard import detect_persistent_secret
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.screen_awareness import ScreenAnalysisResult, ScreenAwarenessService, VisualTarget
from app.services.screen_change_detection import compare_captured_frames
from app.services.windows_accessibility import locate_control_with_windows_accessibility
from app.services.windows_receiver import (
    activate_window,
    get_verified_receiver,
    remember_verified_receiver,
    top_visible_window,
    window_at_cursor,
    window_at_point,
)


_KEY_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:press|hit)\s+"
    r"(enter|return|escape|esc|tab|backspace|arrow\s+up|up\s+arrow|arrow\s+down|down\s+arrow)\s*$",
    re.IGNORECASE,
)
_ENTER_CONFIRM_RE = re.compile(r"^(?:yes[,.]?\s*)?confirm\s+enter$", re.IGNORECASE)
_SEARCH_CONFIRM_RE = re.compile(r"^(?:yes[,.]?\s*)?confirm\s+search$", re.IGNORECASE)
_CANCEL_RE = re.compile(
    r"^(?:cancel(?:\s+(?:enter|search))?|no|never\s*mind|nevermind|stop)$",
    re.IGNORECASE,
)
_BROWSER_SEARCH_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:open|launch)\s+(?:microsoft\s+)?edge(?:\s+browser)?\s*"
    r"(?:,|;|\band\b|\bthen\b)\s*(?:search(?:\s+the\s+web)?\s+(?:for\s+)?)?(.+?)\s*$",
    re.IGNORECASE,
)
_SEARCH_EDGE_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?search(?:\s+the\s+web)?\s+for\s+(.+?)\s+(?:in|using|with)\s+"
    r"(?:microsoft\s+)?edge(?:\s+browser)?\s*$",
    re.IGNORECASE,
)

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
_EDGE_ADDRESS_BAR = "Address and search bar"


@dataclass(frozen=True, slots=True)
class KeyboardRequest:
    key: str


@dataclass(frozen=True, slots=True)
class BrowserSearchRequest:
    query: str


@dataclass(frozen=True, slots=True)
class WindowContext:
    hwnd: int
    title: str
    source: str = "unknown"


@dataclass(frozen=True, slots=True)
class PendingEnter:
    hwnd: int
    title: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PendingBrowserSearch:
    query: str
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


class PendingBrowserSearchStore:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl = timedelta(seconds=max(30, ttl_seconds))
        self._pending: dict[str, PendingBrowserSearch] = {}

    def stage(self, user_id: str, query: str) -> PendingBrowserSearch:
        now = datetime.now(timezone.utc)
        pending = PendingBrowserSearch(
            query=query,
            title="Microsoft Edge search",
            created_at=now,
            expires_at=now + self.ttl,
        )
        self._pending[user_id] = pending
        return pending

    def get(self, user_id: str) -> PendingBrowserSearch | None:
        pending = self._pending.get(user_id)
        if pending is None:
            return None
        if pending.expires_at <= datetime.now(timezone.utc):
            self._pending.pop(user_id, None)
            return None
        return pending

    def pop(self, user_id: str) -> PendingBrowserSearch | None:
        pending = self.get(user_id)
        self._pending.pop(user_id, None)
        return pending

    def cancel(self, user_id: str) -> PendingBrowserSearch | None:
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


def _clean_search_query(raw: str) -> str:
    query = raw.strip().strip(" .")
    if len(query) >= 2 and query[0] == query[-1] and query[0] in {'"', "'"}:
        query = query[1:-1].strip()
    return query


def parse_browser_search_request(text: str) -> BrowserSearchRequest | None:
    raw = text.strip()
    if not raw or raw.endswith("?"):
        return None
    match = _BROWSER_SEARCH_RE.match(raw) or _SEARCH_EDGE_RE.match(raw)
    if match is None:
        return None
    query = _clean_search_query(match.group(1))
    if not query or len(query) > 300:
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in query):
        return None
    return BrowserSearchRequest(query=query)


def is_enter_confirmation(text: str) -> bool:
    return bool(_ENTER_CONFIRM_RE.match(text.strip()))


def is_search_confirmation(text: str) -> bool:
    return bool(_SEARCH_CONFIRM_RE.match(text.strip()))


def is_keyboard_cancellation(text: str) -> bool:
    return bool(_CANCEL_RE.match(text.strip()))


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


def _physical_center(analysis: ScreenAnalysisResult, target: VisualTarget) -> tuple[int, int]:
    bbox = target.bbox_normalized
    if bbox is None:
        raise ValueError("The address bar did not provide a usable bounding box")
    left, top, right, bottom = bbox
    x = analysis.capture_left + int(round(analysis.capture_width * ((left + right) / 2.0) / 1000.0))
    y = analysis.capture_top + int(round(analysis.capture_height * ((top + bottom) / 2.0) / 1000.0))
    return x, y


class KeyboardInteractionService:
    """Controlled keyboard actions plus the first Phase 5C.4 fixed browser workflow.

    The special-key surface remains restricted to six named single keys. The browser
    workflow is not a free-form agent loop: it supports one deterministic Edge search
    plan, opens/focuses Edge, stages the exact search text, requires ``confirm search``,
    then freshly re-locates the address bar, replaces its value, presses Enter once,
    verifies a visible change, and stops on the results page.
    """

    def __init__(
        self,
        screen: ScreenAwarenessService,
        tools: ToolRegistry,
        *,
        context_provider: Callable[[], WindowContext | None] | None = None,
    ) -> None:
        self.screen = screen
        self.tools = tools
        self.context_provider = context_provider
        self.pending = PendingEnterStore(ttl_seconds=120)
        self.pending_search = PendingBrowserSearchStore(ttl_seconds=120)

    def has_pending(self, user_id: str) -> bool:
        return self.pending.get(user_id) is not None or self.pending_search.get(user_id) is not None

    def cancel_pending(self, user_id: str) -> PendingEnter | PendingBrowserSearch | None:
        search = self.pending_search.cancel(user_id)
        if search is not None:
            return search
        return self.pending.cancel(user_id)

    def can_handle(self, message: ChatMessage) -> bool:
        pending_search = self.pending_search.get(message.user_id)
        pending_enter = self.pending.get(message.user_id)
        if pending_search is not None and (
            is_search_confirmation(message.content) or is_keyboard_cancellation(message.content)
        ):
            return True
        if pending_enter is not None and (
            is_enter_confirmation(message.content) or is_keyboard_cancellation(message.content)
        ):
            return True
        return (
            parse_browser_search_request(message.content) is not None
            or parse_keyboard_request(message.content) is not None
        )

    def _hide_sarah(self) -> int | None:
        hide = getattr(self.screen, "_hide_sarah_if_foreground", None)
        return hide() if callable(hide) else None

    def _restore_sarah(self, hwnd: int | None) -> None:
        restore = getattr(self.screen, "_restore_sarah_window", None)
        if callable(restore):
            restore(hwnd)

    def _resolve_receiver(self, hidden_sarah_hwnd: int | None) -> WindowContext | None:
        if self.context_provider is not None:
            return self.context_provider()

        remembered = get_verified_receiver()
        if remembered is not None and remembered.hwnd != int(hidden_sarah_hwnd or 0):
            return WindowContext(
                hwnd=remembered.hwnd,
                title=remembered.title,
                source="recent_verified_visual_receiver",
            )

        candidate = window_at_cursor(exclude_hwnd=hidden_sarah_hwnd)
        source = "pointer_target"
        if candidate is None:
            candidate = top_visible_window(exclude_hwnd=hidden_sarah_hwnd)
            source = "z_order_fallback"
        if candidate is None:
            return None
        hwnd, title = candidate
        return WindowContext(hwnd=hwnd, title=title, source=source)

    def _activate_receiver(self, context: WindowContext) -> bool:
        if self.context_provider is not None:
            return True
        return activate_window(context.hwnd)

    def _refresh_receiver(self, context: WindowContext) -> None:
        if self.context_provider is not None:
            return
        remember_verified_receiver(
            context.hwnd,
            context.title,
            source="controlled_keyboard_continuation",
            ttl_seconds=180,
        )

    async def _capture_data_url(self) -> str | None:
        capture = getattr(self.screen, "_capture", None)
        if not callable(capture):
            return None
        try:
            frame = await capture()
        except Exception:
            return None
        return getattr(frame, "data_url", None)

    async def _locate_edge_address_bar(self) -> tuple[ScreenAnalysisResult, VisualTarget] | None:
        if not isinstance(self.screen, ScreenAwarenessService):
            return None
        for attempt in range(10):
            analysis = await locate_control_with_windows_accessibility(self.screen, _EDGE_ADDRESS_BAR)
            if analysis is not None and analysis.targets:
                target = analysis.targets[0]
                if target.bbox_normalized is not None and "password" not in target.role.lower():
                    return analysis, target
            if attempt < 9:
                await asyncio.sleep(0.35)
        return None

    async def _stage_browser_search(self, message: ChatMessage, request: BrowserSearchRequest) -> AssistantReply:
        if detect_persistent_secret(value=request.query) is not None:
            return AssistantReply(
                text="I won't submit a search query that appears to contain a password, API key, token, private key, or other credential.",
                emotion="concerned",
                should_speak=True,
            )

        result = await self.tools.invoke(
            ToolInvocation(
                tool_name="open_app",
                arguments={"app": "edge"},
                requested_by="phase5c4_edge_search_workflow",
            )
        )
        if not result.ok:
            return AssistantReply(
                text=f"I couldn't open or focus Microsoft Edge safely: {result.error or 'the app launch was rejected.'}",
                emotion="concerned",
                should_speak=True,
            )

        located = await self._locate_edge_address_bar()
        if located is None:
            return AssistantReply(
                text="I opened Microsoft Edge, but Windows UI Automation did not expose its address bar reliably enough to stage the search. I did not type or submit anything.",
                emotion="concerned",
                should_speak=True,
            )

        self.pending_search.stage(message.user_id, request.query)
        return AssistantReply(
            text=(
                f'I opened Microsoft Edge and verified its address bar. I have not typed or submitted the search for "{request.query}". '
                'Reply "confirm search" within 2 minutes to replace the address bar with exactly that query and press Enter once, or "cancel".'
            ),
            emotion="concerned",
            should_speak=True,
        )

    async def _execute_confirmed_search(self, user_id: str, pending: PendingBrowserSearch) -> AssistantReply:
        located = await self._locate_edge_address_bar()
        if located is None:
            self.pending_search.cancel(user_id)
            return AssistantReply(
                text="I did not run the search because I could not freshly re-verify Microsoft Edge's address bar.",
                emotion="concerned",
                should_speak=True,
            )

        analysis, target = located
        x, y = _physical_center(analysis, target)
        hidden_hwnd: int | None = None
        replace_result: ToolResult | None = None
        enter_result: ToolResult | None = None
        receiver: tuple[int, str] | None = None
        before_data_url: str | None = None
        after_data_url: str | None = None
        try:
            hidden_hwnd = self._hide_sarah()
            if hidden_hwnd is not None:
                await asyncio.sleep(0.25)

            receiver = window_at_point(x, y, exclude_hwnd=hidden_hwnd)
            if receiver is None:
                self.pending_search.cancel(user_id)
                return AssistantReply(
                    text="I did not run the search because I could not verify which application window owns the Edge address bar.",
                    emotion="concerned",
                    should_speak=True,
                )

            replace_result = await self.tools.invoke(
                ToolInvocation(
                    tool_name="replace_text_value",
                    arguments={
                        "target_query": _EDGE_ADDRESS_BAR,
                        "text": pending.query,
                        "expected_x": x,
                        "expected_y": y,
                    },
                    requested_by="confirmed_phase5c4_edge_search_text",
                ),
                confirmed=True,
            )
            if not replace_result.ok:
                self.pending_search.cancel(user_id)
                return AssistantReply(
                    text=f"I did not submit the search because the confirmed address-bar replacement failed: {replace_result.error or 'Windows rejected it.'}",
                    emotion="concerned",
                    should_speak=True,
                )

            remember_verified_receiver(
                receiver[0],
                receiver[1],
                source="confirmed_edge_search_workflow",
                ttl_seconds=180,
            )
            context = WindowContext(hwnd=receiver[0], title=receiver[1], source="confirmed_edge_search_workflow")
            if not self._activate_receiver(context):
                self.pending_search.cancel(user_id)
                return AssistantReply(
                    text="I replaced the Edge address bar, but I did not press Enter because Windows would not verify Edge as the receiving window.",
                    emotion="concerned",
                    should_speak=True,
                )

            before_data_url = await self._capture_data_url()
            enter_result = await self.tools.invoke(
                ToolInvocation(
                    tool_name="press_enter",
                    arguments={},
                    requested_by="confirmed_phase5c4_edge_search_submit",
                ),
                confirmed=True,
            )
            if enter_result.ok:
                await asyncio.sleep(0.45)
                after_data_url = await self._capture_data_url()
        finally:
            self._restore_sarah(hidden_hwnd)

        self.pending_search.cancel(user_id)
        if enter_result is None or not enter_result.ok:
            error = enter_result.error if enter_result is not None else "The Enter controller did not return a result."
            return AssistantReply(
                text=f"I replaced the Edge address bar but did not complete the search submission: {error or 'Windows rejected Enter.'}",
                emotion="concerned",
                should_speak=True,
            )

        verification = _verification_text(before_data_url, after_data_url)
        return AssistantReply(
            text=(
                f'Completed the confirmed Edge search for "{pending.query}". I replaced the verified address bar, pressed Enter once, '
                f"and stopped on the resulting page. Verification: {verification}"
            ),
            emotion="calm",
            should_speak=True,
        )

    async def _peek_underlying_context(self) -> WindowContext | None:
        hidden_hwnd: int | None = None
        try:
            hidden_hwnd = self._hide_sarah()
            if hidden_hwnd is not None:
                await asyncio.sleep(0.25)
            context = self._resolve_receiver(hidden_hwnd)
            if context is None or not self._activate_receiver(context):
                return None
            return context
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
                    text="I did not press the key because I could not identify a recently verified application receiver.",
                    emotion="concerned",
                    should_speak=True,
                )
            if not self._activate_receiver(context):
                return AssistantReply(
                    text=f'I did not press the key because Windows would not give keyboard focus to "{context.title}".',
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
                self._refresh_receiver(context)
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
        target = context.title if context is not None else "the verified application"
        verification = _verification_text(before_data_url, after_data_url)
        return AssistantReply(
            text=(
                f'Pressed {display} once in the verified receiver window "{target}". '
                f"No modifiers or hotkeys were used. Verification: {verification}"
            ),
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
                actual = fresh_context.title if fresh_context is not None else "no identifiable receiver"
                return AssistantReply(
                    text=(
                        f'I did not press Enter because the verified receiving window changed. It was staged for "{pending.title}", '
                        f'but the current verified receiver is {actual!r}. Please request Enter again from the current screen.'
                    ),
                    emotion="concerned",
                    should_speak=True,
                )
            if not self._activate_receiver(fresh_context):
                self.pending.cancel(user_id)
                return AssistantReply(
                    text=f'I did not press Enter because Windows would not give keyboard focus to the staged "{pending.title}" window.',
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
                self._refresh_receiver(fresh_context)
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
            text=f'Pressed Enter once in the freshly re-verified receiver window "{target}". Verification: {verification}',
            emotion="calm",
            should_speak=True,
        )

    async def handle(self, message: ChatMessage, *, other_system_change_pending: bool = False) -> AssistantReply | None:
        user_id = message.user_id
        pending_search = self.pending_search.get(user_id)
        pending_enter = self.pending.get(user_id)

        if pending_search is not None and is_keyboard_cancellation(message.content):
            self.pending_search.cancel(user_id)
            return AssistantReply(
                text=f'Cancelled. I did not type or submit the Edge search for "{pending_search.query}".',
                emotion="calm",
                should_speak=True,
            )
        if pending_search is not None and is_search_confirmation(message.content):
            pending_search = self.pending_search.pop(user_id)
            if pending_search is None:
                return AssistantReply(
                    text="That search confirmation expired. Please request the Edge search again.",
                    emotion="concerned",
                    should_speak=True,
                )
            # Re-stage internally while execution is in progress so unrelated state
            # cannot be mistaken for a free confirmation.
            self.pending_search.stage(user_id, pending_search.query)
            return await self._execute_confirmed_search(user_id, pending_search)

        if pending_enter is not None and is_keyboard_cancellation(message.content):
            self.pending.cancel(user_id)
            return AssistantReply(
                text=f'Cancelled. I did not press Enter in "{pending_enter.title}".',
                emotion="calm",
                should_speak=True,
            )
        if pending_enter is not None and is_enter_confirmation(message.content):
            return await self._execute_confirmed_enter(user_id, pending_enter)

        browser_request = parse_browser_search_request(message.content)
        keyboard_request = parse_keyboard_request(message.content)

        if pending_search is not None:
            return AssistantReply(
                text='An Edge search is already staged. Reply "confirm search" or "cancel" before requesting another controlled action.',
                emotion="concerned",
                should_speak=True,
            )
        if pending_enter is not None:
            return AssistantReply(
                text=(
                    f'Enter is already staged for "{pending_enter.title}". Reply "confirm enter" or "cancel" '
                    "before requesting another controlled action."
                ),
                emotion="concerned",
                should_speak=True,
            )

        if browser_request is not None:
            if other_system_change_pending:
                return AssistantReply(
                    text="You already have another pending system change. Confirm or cancel it before staging the Edge search workflow.",
                    emotion="concerned",
                    should_speak=True,
                )
            return await self._stage_browser_search(message, browser_request)

        if keyboard_request is None:
            return None

        if other_system_change_pending:
            return AssistantReply(
                text="You already have another pending system change. Confirm or cancel it before using controlled keyboard input.",
                emotion="concerned",
                should_speak=True,
            )

        if keyboard_request.key == "enter":
            context = await self._peek_underlying_context()
            if context is None:
                return AssistantReply(
                    text="I did not stage Enter because I could not identify and focus a recently verified application receiver.",
                    emotion="concerned",
                    should_speak=True,
                )
            self.pending.stage(user_id, context)
            return AssistantReply(
                text=(
                    f'Enter is staged for the verified receiver window "{context.title}", but I have not pressed it. '
                    'Enter can submit, send, search, navigate, purchase, install, or confirm an action depending on focus. '
                    'Reply "confirm enter" within 2 minutes to re-verify that same receiver and press Enter once, or "cancel".'
                ),
                emotion="concerned",
                should_speak=True,
            )

        return await self._execute_safe_key(keyboard_request.key)
