from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.agent.contracts import ToolInvocation, ToolResult
from app.agent.tool_registry import ToolRegistry
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.screen_awareness import ScreenAnalysisResult, ScreenAwarenessError, ScreenAwarenessService, VisualTarget
from app.services.visual_grounding import locate_control_with_plain_vision
from app.services.windows_accessibility import locate_control_with_windows_accessibility


_CLICK_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:click|press|select|choose)\s+(?:on\s+)?(?:the\s+)?(.+?)\s*$",
    re.IGNORECASE,
)
_MOVE_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:move\s+(?:the\s+)?(?:mouse|cursor|pointer)\s+(?:to|over)|hover\s+(?:over|on))\s+(?:the\s+)?(.+?)\s*$",
    re.IGNORECASE,
)
_TYPE_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?type\s+(.+?)\s+(?:into|in)\s+(?:the\s+)?(.+?)\s*$",
    re.IGNORECASE,
)
_SCROLL_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?scroll\s+(up|down)(?:\s+(\d+)(?:\s+(?:steps?|notches?))?)?\s*$",
    re.IGNORECASE,
)
_CLICK_CONFIRM_RE = re.compile(
    r"^(?:yes[,.]?\s*)?(?:confirm(?:\s+click)?|click\s+it|do\s+the\s+click|go\s+ahead(?:\s+and\s+click)?)$",
    re.IGNORECASE,
)
_TYPE_CONFIRM_RE = re.compile(
    r"^(?:yes[,.]?\s*)?(?:confirm\s+type|type\s+it|go\s+ahead\s+and\s+type)$",
    re.IGNORECASE,
)
_STRONG_CONFIRM_RE = re.compile(r"^confirm\s+consequential\s+click$", re.IGNORECASE)
_CANCEL_RE = re.compile(r"^(?:cancel(?:\s+(?:click|type))?|no|never\s*mind|nevermind|stop)$", re.IGNORECASE)
_GENERIC_TARGETS = {
    "it",
    "that",
    "this",
    "button",
    "the button",
    "control",
    "the control",
    "something",
}
_UI_WORDS = {
    "button",
    "link",
    "tab",
    "checkbox",
    "option",
    "menu",
    "item",
    "field",
    "box",
    "textbox",
    "control",
    "icon",
    "the",
    "a",
    "an",
}
_CONSEQUENTIAL_WORDS = {
    "delete",
    "remove",
    "erase",
    "uninstall",
    "install",
    "buy",
    "purchase",
    "pay",
    "checkout",
    "submit",
    "send",
    "authorize",
    "authorise",
    "grant",
    "permission",
    "permissions",
    "allow",
    "reset",
    "factory",
    "format",
    "wipe",
    "confirm purchase",
    "place order",
}
_SENSITIVE_INPUT_WORDS = {
    "password",
    "passcode",
    "pin",
    "security code",
    "verification code",
    "one time code",
    "one-time code",
    "otp",
    "cvv",
    "social security",
    "ssn",
    "api key",
    "access token",
    "secret",
}
_TEXT_ENTRY_ROLES = ("edit", "textbox", "text box", "field", "combobox", "combo box", "document", "input")
_MAX_SCROLL_STEPS = 5
_DEFAULT_SCROLL_STEPS = 3


@dataclass(frozen=True, slots=True)
class VisualInteractionRequest:
    action: str
    target: str = ""
    text: str = ""
    direction: str = ""
    steps: int = 0


@dataclass(frozen=True, slots=True)
class PendingVisualAction:
    action: str
    target_query: str
    initial_label: str
    initial_visible_text: str
    initial_bbox: tuple[int, int, int, int]
    initial_confidence: float | None
    consequential: bool
    text: str
    created_at: datetime
    expires_at: datetime


class PendingVisualActionStore:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl = timedelta(seconds=max(30, ttl_seconds))
        self._pending: dict[str, PendingVisualAction] = {}

    def stage(
        self,
        user_id: str,
        *,
        action: str,
        target_query: str,
        target: VisualTarget,
        consequential: bool = False,
        text: str = "",
    ) -> PendingVisualAction:
        if target.bbox_normalized is None:
            raise ValueError("A visual action cannot be staged without a target bounding box")
        now = datetime.now(timezone.utc)
        pending = PendingVisualAction(
            action=action,
            target_query=target_query,
            initial_label=target.label,
            initial_visible_text=target.visible_text,
            initial_bbox=target.bbox_normalized,
            initial_confidence=target.confidence,
            consequential=consequential,
            text=text,
            created_at=now,
            expires_at=now + self.ttl,
        )
        self._pending[user_id] = pending
        return pending

    def get(self, user_id: str) -> PendingVisualAction | None:
        pending = self._pending.get(user_id)
        if pending is None:
            return None
        if pending.expires_at <= datetime.now(timezone.utc):
            self._pending.pop(user_id, None)
            return None
        return pending

    def pop(self, user_id: str) -> PendingVisualAction | None:
        pending = self.get(user_id)
        self._pending.pop(user_id, None)
        return pending

    def cancel(self, user_id: str) -> PendingVisualAction | None:
        return self._pending.pop(user_id, None)


def _clean_target(raw: str) -> str:
    target = raw.strip().strip(" .,!;:").strip('"').strip("'").strip()
    target = re.sub(r"\s+(?:please|for me)$", "", target, flags=re.IGNORECASE).strip()
    without_role = re.sub(
        r"\s+(?:button|link|tab|checkbox|option|menu\s+item|field|search\s+box|textbox|control|icon)$",
        "",
        target,
        flags=re.IGNORECASE,
    ).strip()
    if without_role:
        target = without_role
    return target.strip().strip('"').strip("'").strip()


def _clean_literal_text(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


def parse_visual_interaction_request(text: str) -> VisualInteractionRequest | None:
    raw = text.strip()
    if not raw or raw.endswith("?"):
        return None

    scroll = _SCROLL_RE.match(raw)
    if scroll:
        steps = int(scroll.group(2)) if scroll.group(2) else _DEFAULT_SCROLL_STEPS
        return VisualInteractionRequest(action="scroll", direction=scroll.group(1).lower(), steps=steps)

    typed = _TYPE_RE.match(raw)
    if typed:
        literal = _clean_literal_text(typed.group(1))
        target = _clean_target(typed.group(2))
        if literal and target and target.lower() not in _GENERIC_TARGETS:
            return VisualInteractionRequest(action="type", target=target, text=literal)
        return None

    move = _MOVE_RE.match(raw)
    if move:
        target = _clean_target(move.group(1))
        if target and target.lower() not in _GENERIC_TARGETS:
            return VisualInteractionRequest(action="move", target=target)
        return None

    click = _CLICK_RE.match(raw)
    if click:
        target = _clean_target(click.group(1))
        if target and target.lower() not in _GENERIC_TARGETS:
            return VisualInteractionRequest(action="click", target=target)
    return None


def is_visual_confirmation(text: str) -> bool:
    raw = text.strip()
    return bool(_CLICK_CONFIRM_RE.match(raw) or _TYPE_CONFIRM_RE.match(raw) or _STRONG_CONFIRM_RE.match(raw))


def is_strong_visual_confirmation(text: str) -> bool:
    return bool(_STRONG_CONFIRM_RE.match(text.strip()))


def is_visual_cancellation(text: str) -> bool:
    return bool(_CANCEL_RE.match(text.strip()))


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _UI_WORDS and len(token) > 1
    }


def _target_match_score(query: str, target: VisualTarget) -> float:
    requested = _tokens(query)
    candidate = _tokens(" ".join(part for part in (target.label, target.visible_text) if part))
    if not requested:
        return 0.0
    overlap = len(requested & candidate) / len(requested)
    confidence = target.confidence if target.confidence is not None else 0.5
    return overlap * 0.75 + confidence * 0.25


def _best_target(query: str, targets: Iterable[VisualTarget]) -> tuple[VisualTarget | None, float]:
    best: VisualTarget | None = None
    best_score = 0.0
    for target in targets:
        if target.bbox_normalized is None:
            continue
        score = _target_match_score(query, target)
        if score > best_score:
            best, best_score = target, score
    return best, best_score


def _physical_center(analysis: ScreenAnalysisResult, target: VisualTarget) -> tuple[int, int]:
    bbox = target.bbox_normalized
    if bbox is None:
        raise ValueError("The visual target does not have a usable bounding box")
    left, top, right, bottom = bbox
    center_x = (left + right) / 2.0
    center_y = (top + bottom) / 2.0
    x = analysis.capture_left + int(round(analysis.capture_width * center_x / 1000.0))
    y = analysis.capture_top + int(round(analysis.capture_height * center_y / 1000.0))
    return x, y


def _consequential_from_text(*parts: str) -> bool:
    joined = " ".join(parts).lower()
    return any(word in joined for word in _CONSEQUENTIAL_WORDS)


def _sensitive_input_target(*parts: str) -> bool:
    joined = " ".join(parts).lower()
    return any(word in joined for word in _SENSITIVE_INPUT_WORDS)


def _target_accepts_text(target: VisualTarget) -> bool:
    role = target.role.lower()
    return any(marker in role for marker in _TEXT_ENTRY_ROLES)


def _target_identity_matches(pending: PendingVisualAction, fresh: VisualTarget) -> bool:
    original = " ".join(part for part in (pending.initial_label, pending.initial_visible_text) if part)
    original_tokens = _tokens(original) or _tokens(pending.target_query)
    fresh_tokens = _tokens(" ".join(part for part in (fresh.label, fresh.visible_text) if part))
    if not original_tokens or not fresh_tokens:
        return False
    overlap = len(original_tokens & fresh_tokens) / max(1, len(original_tokens))
    return overlap >= 0.5


class VisualInteractionService:
    """Coordinate Phase 5C pointer, click, literal typing, and bounded scrolling.

    Standard Windows controls are located through Windows UI Automation first. Vision
    is a fallback for applications that do not expose a useful accessibility tree.
    Raw coordinates and arbitrary key sequences are never accepted from the user or a
    language model; physical input still executes through the ToolRegistry boundary.
    """

    def __init__(self, screen: ScreenAwarenessService, tools: ToolRegistry) -> None:
        self.screen = screen
        self.tools = tools
        self.pending = PendingVisualActionStore(ttl_seconds=120)

    def has_pending(self, user_id: str) -> bool:
        return self.pending.get(user_id) is not None

    def cancel_pending(self, user_id: str) -> PendingVisualAction | None:
        return self.pending.cancel(user_id)

    def can_handle(self, message: ChatMessage) -> bool:
        if self.has_pending(message.user_id) and (
            is_visual_confirmation(message.content) or is_visual_cancellation(message.content)
        ):
            return True
        return parse_visual_interaction_request(message.content) is not None

    async def _locate(self, target_query: str) -> tuple[ScreenAnalysisResult, VisualTarget, float]:
        if isinstance(self.screen, ScreenAwarenessService):
            analysis = await locate_control_with_windows_accessibility(self.screen, target_query)
            if analysis is None:
                analysis = await locate_control_with_plain_vision(self.screen, target_query)
        else:
            prompt = (
                f'Find the button, field, link, tab, checkbox, menu item, icon, or other visible UI control labeled "{target_query}" on my screen. '
                "Return a target only if you can identify it confidently from the screenshot."
            )
            analysis = await self.screen.analyze(prompt)

        target, score = _best_target(target_query, analysis.targets)
        if target is None or target.bbox_normalized is None or score < 0.55:
            detail = analysis.text.strip()
            raise ScreenAwarenessError(
                f'I can see the desktop, but I cannot locate "{target_query}" confidently enough to control the pointer.'
                + (f" Locator result: {detail}" if detail else "")
            )
        return analysis, target, score

    async def _move_to(self, analysis: ScreenAnalysisResult, target: VisualTarget) -> tuple[int, int]:
        x, y = _physical_center(analysis, target)
        result = await self.tools.invoke(
            ToolInvocation(
                tool_name="move_pointer",
                arguments={"x": x, "y": y},
                requested_by="visual_interaction_coordinator",
            )
        )
        if not result.ok:
            raise ScreenAwarenessError(result.error or "Windows did not move the pointer to the target")
        return x, y

    def _hide_sarah_for_input(self) -> int | None:
        hide = getattr(self.screen, "_hide_sarah_if_foreground", None)
        if callable(hide):
            return hide()
        return None

    def _restore_sarah_after_input(self, hwnd: int | None) -> None:
        restore = getattr(self.screen, "_restore_sarah_window", None)
        if callable(restore):
            restore(hwnd)

    async def _verify(self, prompt: str) -> str:
        try:
            verification = await self.screen.analyze(prompt)
            return verification.text.strip()
        except ScreenAwarenessError as exc:
            return f"I could not visually verify the result: {exc}"

    async def _execute_confirmed_click(self, pending: PendingVisualAction) -> AssistantReply:
        try:
            fresh_analysis, fresh_target, _score = await self._locate(pending.target_query)
        except ScreenAwarenessError as exc:
            return AssistantReply(
                text=f"I did not click because I could not re-verify the target from the current desktop: {exc}",
                emotion="concerned",
                should_speak=True,
            )

        if not _target_identity_matches(pending, fresh_target):
            return AssistantReply(
                text=(
                    f'I did not click because the fresh target no longer matches the staged "{pending.target_query}" control. '
                    "Please request the click again from the current screen."
                ),
                emotion="concerned",
                should_speak=True,
            )

        x, y = _physical_center(fresh_analysis, fresh_target)
        hidden_hwnd: int | None = None
        click_result: ToolResult | None = None
        try:
            hidden_hwnd = self._hide_sarah_for_input()
            if hidden_hwnd is not None:
                await asyncio.sleep(0.25)
            click_result = await self.tools.invoke(
                ToolInvocation(
                    tool_name="click_pointer",
                    arguments={"x": x, "y": y},
                    requested_by="confirmed_visual_interaction_coordinator",
                ),
                confirmed=True,
            )
            if click_result.ok:
                await asyncio.sleep(0.45)
        finally:
            self._restore_sarah_after_input(hidden_hwnd)

        if click_result is None or not click_result.ok:
            error = click_result.error if click_result is not None else "The click controller did not return a result."
            return AssistantReply(
                text=f"I did not complete the click: {error or 'Windows rejected the click.'}",
                emotion="concerned",
                should_speak=True,
            )

        verification_text = await self._verify(
            f'Look at my screen after a single click on "{pending.target_query}". '
            "Briefly describe the visible result and whether the interface appears to have responded. "
            "Do not assume success if the visible evidence is unclear."
        )
        label = fresh_target.visible_text or fresh_target.label or pending.target_query
        return AssistantReply(
            text=f'Clicked "{label}" once at the freshly verified target. Verification: {verification_text}',
            emotion="calm",
            should_speak=True,
        )

    async def _execute_confirmed_type(self, pending: PendingVisualAction) -> AssistantReply:
        try:
            fresh_analysis, fresh_target, _score = await self._locate(pending.target_query)
        except ScreenAwarenessError as exc:
            return AssistantReply(
                text=f"I did not type because I could not re-verify the target from the current desktop: {exc}",
                emotion="concerned",
                should_speak=True,
            )

        if not _target_identity_matches(pending, fresh_target):
            return AssistantReply(
                text=(
                    f'I did not type because the fresh target no longer matches the staged "{pending.target_query}" field. '
                    "Please request the typing action again from the current screen."
                ),
                emotion="concerned",
                should_speak=True,
            )
        if _sensitive_input_target(pending.target_query, fresh_target.label, fresh_target.visible_text, fresh_target.role):
            return AssistantReply(
                text="I will not type into a password, PIN, verification-code, token, or other secret-entry field in this phase.",
                emotion="concerned",
                should_speak=True,
            )
        if not _target_accepts_text(fresh_target):
            return AssistantReply(
                text=f'I did not type because "{fresh_target.visible_text or fresh_target.label}" is not exposed as a text-entry control.',
                emotion="concerned",
                should_speak=True,
            )

        x, y = _physical_center(fresh_analysis, fresh_target)
        hidden_hwnd: int | None = None
        click_result: ToolResult | None = None
        type_result: ToolResult | None = None
        try:
            hidden_hwnd = self._hide_sarah_for_input()
            if hidden_hwnd is not None:
                await asyncio.sleep(0.25)
            click_result = await self.tools.invoke(
                ToolInvocation(
                    tool_name="click_pointer",
                    arguments={"x": x, "y": y},
                    requested_by="confirmed_visual_type_focus",
                ),
                confirmed=True,
            )
            if click_result.ok:
                await asyncio.sleep(0.12)
                type_result = await self.tools.invoke(
                    ToolInvocation(
                        tool_name="type_text",
                        arguments={"text": pending.text},
                        requested_by="confirmed_visual_type_coordinator",
                    ),
                    confirmed=True,
                )
                if type_result.ok:
                    await asyncio.sleep(0.35)
        finally:
            self._restore_sarah_after_input(hidden_hwnd)

        if click_result is None or not click_result.ok:
            error = click_result.error if click_result is not None else "The focus click did not return a result."
            return AssistantReply(
                text=f"I did not type because I could not focus the verified field: {error or 'Windows rejected the focus click.'}",
                emotion="concerned",
                should_speak=True,
            )
        if type_result is None or not type_result.ok:
            error = type_result.error if type_result is not None else "The typing controller did not return a result."
            return AssistantReply(
                text=f"I focused the field but did not complete the typing action: {error or 'Windows rejected the literal text input.'}",
                emotion="concerned",
                should_speak=True,
            )

        verification_text = await self._verify(
            f'Look at my screen after literal text was typed into "{pending.target_query}". '
            "Briefly say whether the field visibly changed. Do not repeat the exact entered text and do not imply Enter/Submit was pressed."
        )
        label = fresh_target.visible_text or fresh_target.label or pending.target_query
        return AssistantReply(
            text=(
                f'Typed the exact requested literal text into "{label}" after re-verifying and focusing the field. '
                f"I did not press Enter, Tab, or any shortcut. Verification: {verification_text}"
            ),
            emotion="calm",
            should_speak=True,
        )

    async def _execute_scroll(self, direction: str, steps: int) -> AssistantReply:
        if steps < 1 or steps > _MAX_SCROLL_STEPS:
            return AssistantReply(
                text=f"A single scroll request is limited to 1-{_MAX_SCROLL_STEPS} steps.",
                emotion="concerned",
                should_speak=True,
            )
        hidden_hwnd: int | None = None
        result: ToolResult | None = None
        try:
            hidden_hwnd = self._hide_sarah_for_input()
            if hidden_hwnd is not None:
                await asyncio.sleep(0.25)
            result = await self.tools.invoke(
                ToolInvocation(
                    tool_name="scroll_pointer",
                    arguments={"direction": direction, "steps": steps},
                    requested_by="visual_scroll_coordinator",
                )
            )
            if result.ok:
                await asyncio.sleep(0.35)
        finally:
            self._restore_sarah_after_input(hidden_hwnd)

        if result is None or not result.ok:
            error = result.error if result is not None else "The scroll controller did not return a result."
            return AssistantReply(
                text=f"I could not complete the bounded scroll: {error or 'Windows rejected the scroll.'}",
                emotion="concerned",
                should_speak=True,
            )
        verification_text = await self._verify(
            f"Look at my screen after a small scroll {direction}. Briefly say whether the visible content appears to have moved."
        )
        return AssistantReply(
            text=f"Scrolled {direction} {steps} bounded step{'s' if steps != 1 else ''}. Verification: {verification_text}",
            emotion="calm",
            should_speak=True,
        )

    async def handle(self, message: ChatMessage, *, other_system_change_pending: bool = False) -> AssistantReply | None:
        user_id = message.user_id
        pending = self.pending.get(user_id)

        if pending is not None and is_visual_cancellation(message.content):
            self.pending.cancel(user_id)
            verb = "click" if pending.action == "click" else "type into"
            return AssistantReply(
                text=f'Cancelled. I did not {verb} "{pending.target_query}".',
                emotion="calm",
                should_speak=True,
            )

        if pending is not None and is_visual_confirmation(message.content):
            raw = message.content.strip()
            if pending.action == "click":
                if pending.consequential and not is_strong_visual_confirmation(raw):
                    return AssistantReply(
                        text=(
                            f'The pending click on "{pending.target_query}" appears consequential. '
                            'Reply exactly "confirm consequential click" to proceed, or "cancel".'
                        ),
                        emotion="concerned",
                        should_speak=True,
                    )
                if not (_CLICK_CONFIRM_RE.match(raw) or _STRONG_CONFIRM_RE.match(raw)):
                    return AssistantReply(
                        text='That confirmation phrase is for a different action. Reply "confirm click" or "cancel".',
                        emotion="concerned",
                        should_speak=True,
                    )
            elif pending.action == "type" and not _TYPE_CONFIRM_RE.match(raw):
                return AssistantReply(
                    text='That confirmation phrase is for a different action. Reply "confirm type" or "cancel".',
                    emotion="concerned",
                    should_speak=True,
                )

            pending = self.pending.pop(user_id)
            if pending is None:
                return AssistantReply(
                    text="That visual action confirmation expired. Please request the action again.",
                    emotion="concerned",
                    should_speak=True,
                )
            if pending.action == "click":
                return await self._execute_confirmed_click(pending)
            if pending.action == "type":
                return await self._execute_confirmed_type(pending)

        request = parse_visual_interaction_request(message.content)
        if request is None:
            return None

        if pending is not None:
            expected = "confirm click" if pending.action == "click" else "confirm type"
            return AssistantReply(
                text=(
                    f'You already have a pending visual {pending.action} action on "{pending.target_query}". '
                    f'Reply "{expected}" or "cancel" before staging another visual action.'
                ),
                emotion="concerned",
                should_speak=True,
            )

        if request.action == "scroll":
            return await self._execute_scroll(request.direction, request.steps)

        if request.action in {"click", "type"} and other_system_change_pending:
            return AssistantReply(
                text="You already have another pending system change. Confirm or cancel that action before staging this visual input.",
                emotion="concerned",
                should_speak=True,
            )

        try:
            analysis, target, _score = await self._locate(request.target)
            await self._move_to(analysis, target)
        except ScreenAwarenessError as exc:
            return AssistantReply(text=str(exc), emotion="concerned", should_speak=True)

        label = target.visible_text or target.label or request.target
        if request.action == "move":
            return AssistantReply(
                text=f'I moved the pointer to the identified "{label}" control. I did not click it.',
                emotion="calm",
                should_speak=True,
            )

        if request.action == "type":
            if _sensitive_input_target(request.target, target.label, target.visible_text, target.role):
                return AssistantReply(
                    text="I found that field, but I will not type into password, PIN, verification-code, token, or other secret-entry fields in this phase.",
                    emotion="concerned",
                    should_speak=True,
                )
            if not _target_accepts_text(target):
                return AssistantReply(
                    text=f'I found "{label}", but Windows does not expose it as a text-entry control, so I will not type into it.',
                    emotion="concerned",
                    should_speak=True,
                )
            self.pending.stage(
                user_id,
                action="type",
                target_query=request.target,
                target=target,
                text=request.text,
            )
            return AssistantReply(
                text=(
                    f'I found "{label}" and moved the pointer to it. I have not focused the field or typed anything. '
                    'Reply "confirm type" within 2 minutes to focus it and type only the exact literal text you supplied, or "cancel".'
                ),
                emotion="concerned",
                should_speak=True,
            )

        consequential = _consequential_from_text(request.target, target.label, target.visible_text)
        self.pending.stage(
            user_id,
            action="click",
            target_query=request.target,
            target=target,
            consequential=consequential,
        )
        if consequential:
            confirmation = 'Reply exactly "confirm consequential click" within 2 minutes to click it, or "cancel".'
            caution = " This appears consequential, so I require the stronger confirmation phrase."
        else:
            confirmation = 'Reply "confirm click" within 2 minutes to click it once, or "cancel".'
            caution = ""

        return AssistantReply(
            text=(
                f'I found "{label}" and moved the pointer to its current location. I have not clicked anything.{caution} '
                + confirmation
            ),
            emotion="concerned",
            should_speak=True,
        )
