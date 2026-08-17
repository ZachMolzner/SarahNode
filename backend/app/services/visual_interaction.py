from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.agent.contracts import ToolInvocation
from app.agent.tool_registry import ToolRegistry
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.screen_awareness import ScreenAnalysisResult, ScreenAwarenessError, ScreenAwarenessService, VisualTarget


_CLICK_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:click|press|select|choose)\s+(?:on\s+)?(?:the\s+)?(.+?)\s*$",
    re.IGNORECASE,
)
_MOVE_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:move\s+(?:the\s+)?(?:mouse|cursor|pointer)\s+(?:to|over)|hover\s+(?:over|on))\s+(?:the\s+)?(.+?)\s*$",
    re.IGNORECASE,
)
_VISUAL_CONFIRM_RE = re.compile(
    r"^(?:yes[,.]?\s*)?(?:confirm(?:\s+click)?|click\s+it|do\s+the\s+click|go\s+ahead(?:\s+and\s+click)?)$",
    re.IGNORECASE,
)
_STRONG_CONFIRM_RE = re.compile(r"^confirm\s+consequential\s+click$", re.IGNORECASE)
_CANCEL_RE = re.compile(r"^(?:cancel(?:\s+click)?|no|never\s*mind|nevermind|stop)$", re.IGNORECASE)
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


@dataclass(frozen=True, slots=True)
class VisualInteractionRequest:
    action: str
    target: str


@dataclass(frozen=True, slots=True)
class PendingVisualClick:
    target_query: str
    initial_label: str
    initial_visible_text: str
    initial_bbox: tuple[int, int, int, int]
    initial_confidence: float | None
    consequential: bool
    created_at: datetime
    expires_at: datetime


class PendingVisualClickStore:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl = timedelta(seconds=max(30, ttl_seconds))
        self._pending: dict[str, PendingVisualClick] = {}

    def stage(
        self,
        user_id: str,
        *,
        target_query: str,
        target: VisualTarget,
        consequential: bool,
    ) -> PendingVisualClick:
        if target.bbox_normalized is None:
            raise ValueError("A visual click cannot be staged without a target bounding box")
        now = datetime.now(timezone.utc)
        pending = PendingVisualClick(
            target_query=target_query,
            initial_label=target.label,
            initial_visible_text=target.visible_text,
            initial_bbox=target.bbox_normalized,
            initial_confidence=target.confidence,
            consequential=consequential,
            created_at=now,
            expires_at=now + self.ttl,
        )
        self._pending[user_id] = pending
        return pending

    def get(self, user_id: str) -> PendingVisualClick | None:
        pending = self._pending.get(user_id)
        if pending is None:
            return None
        if pending.expires_at <= datetime.now(timezone.utc):
            self._pending.pop(user_id, None)
            return None
        return pending

    def pop(self, user_id: str) -> PendingVisualClick | None:
        pending = self.get(user_id)
        self._pending.pop(user_id, None)
        return pending

    def cancel(self, user_id: str) -> PendingVisualClick | None:
        return self._pending.pop(user_id, None)


def _clean_target(raw: str) -> str:
    original = raw.strip().strip(" .,!;:")
    target = original.strip('"').strip("'").strip()
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


def parse_visual_interaction_request(text: str) -> VisualInteractionRequest | None:
    raw = text.strip()
    if not raw or raw.endswith("?"):
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
    return bool(_VISUAL_CONFIRM_RE.match(text.strip()) or _STRONG_CONFIRM_RE.match(text.strip()))


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


def _target_identity_matches(pending: PendingVisualClick, fresh: VisualTarget) -> bool:
    original = " ".join(part for part in (pending.initial_label, pending.initial_visible_text) if part)
    original_tokens = _tokens(original) or _tokens(pending.target_query)
    fresh_tokens = _tokens(" ".join(part for part in (fresh.label, fresh.visible_text) if part))
    if not original_tokens or not fresh_tokens:
        return False
    overlap = len(original_tokens & fresh_tokens) / max(1, len(original_tokens))
    return overlap >= 0.5


class VisualInteractionService:
    """Coordinate Phase 5C visual pointer movement and confirmed single clicks.

    The service never accepts raw user coordinates. Every physical point comes from a
    fresh ScreenAwarenessService localization result and is still executed through the
    ToolRegistry permission boundary.
    """

    def __init__(self, screen: ScreenAwarenessService, tools: ToolRegistry) -> None:
        self.screen = screen
        self.tools = tools
        self.pending = PendingVisualClickStore(ttl_seconds=120)

    def has_pending(self, user_id: str) -> bool:
        return self.pending.get(user_id) is not None

    def cancel_pending(self, user_id: str) -> PendingVisualClick | None:
        return self.pending.cancel(user_id)

    def can_handle(self, message: ChatMessage) -> bool:
        if self.has_pending(message.user_id) and (
            is_visual_confirmation(message.content) or is_visual_cancellation(message.content)
        ):
            return True
        return parse_visual_interaction_request(message.content) is not None

    async def _locate(self, target_query: str) -> tuple[ScreenAnalysisResult, VisualTarget, float]:
        prompt = (
            f'Find the button, field, link, tab, checkbox, menu item, icon, or other visible UI control labeled "{target_query}" on my screen. '
            "Return a target only if you can identify it confidently from the screenshot."
        )
        analysis = await self.screen.analyze(prompt)
        target, score = _best_target(target_query, analysis.targets)
        if target is None or target.bbox_normalized is None or score < 0.55:
            detail = analysis.text.strip()
            raise ScreenAwarenessError(
                f'I can see the screen, but I cannot locate "{target_query}" confidently enough to control the pointer.'
                + (f" Visual analysis: {detail}" if detail else "")
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
            raise ScreenAwarenessError(result.error or "Windows did not move the pointer to the visual target")
        return x, y

    def _hide_sarah_for_click(self) -> int | None:
        hide = getattr(self.screen, "_hide_sarah_if_foreground", None)
        if callable(hide):
            return hide()
        return None

    def _restore_sarah_after_click(self, hwnd: int | None) -> None:
        restore = getattr(self.screen, "_restore_sarah_window", None)
        if callable(restore):
            restore(hwnd)

    async def handle(self, message: ChatMessage, *, other_system_change_pending: bool = False) -> AssistantReply | None:
        user_id = message.user_id
        pending = self.pending.get(user_id)

        if pending is not None and is_visual_cancellation(message.content):
            self.pending.cancel(user_id)
            return AssistantReply(
                text=f'Cancelled. I did not click "{pending.target_query}".',
                emotion="calm",
                should_speak=True,
            )

        if pending is not None and is_visual_confirmation(message.content):
            if pending.consequential and not is_strong_visual_confirmation(message.content):
                return AssistantReply(
                    text=(
                        f'The pending click on "{pending.target_query}" appears consequential. '
                        'Reply exactly "confirm consequential click" to proceed, or "cancel".'
                    ),
                    emotion="concerned",
                    should_speak=True,
                )

            pending = self.pending.pop(user_id)
            if pending is None:
                return AssistantReply(
                    text="That visual click confirmation expired. Please request the click again.",
                    emotion="concerned",
                    should_speak=True,
                )

            try:
                fresh_analysis, fresh_target, _score = await self._locate(pending.target_query)
            except ScreenAwarenessError as exc:
                return AssistantReply(
                    text=f"I did not click because I could not re-verify the target on a fresh screen capture: {exc}",
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
                # Fresh screen analysis restores SarahNode so the user can see the
                # confirmation response. Hide it again for the physical click so its
                # window cannot intercept a coordinate intended for the app beneath.
                hidden_hwnd = self._hide_sarah_for_click()
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
                self._restore_sarah_after_click(hidden_hwnd)

            if click_result is None or not click_result.ok:
                error = click_result.error if click_result is not None else "The click controller did not return a result."
                return AssistantReply(
                    text=f"I did not complete the click: {error or 'Windows rejected the click.'}",
                    emotion="concerned",
                    should_speak=True,
                )

            verification_text = ""
            try:
                verification = await self.screen.analyze(
                    f'Look at my screen after a single click on "{pending.target_query}". '
                    "Briefly describe the visible result and whether the interface appears to have responded. "
                    "Do not assume success if the visible evidence is unclear."
                )
                verification_text = verification.text.strip()
            except ScreenAwarenessError as exc:
                verification_text = f"I could not visually verify the result: {exc}"

            label = fresh_target.visible_text or fresh_target.label or pending.target_query
            return AssistantReply(
                text=(
                    f'Clicked "{label}" once at the freshly verified target. '
                    f"Verification: {verification_text}"
                ),
                emotion="calm",
                should_speak=True,
            )

        request = parse_visual_interaction_request(message.content)
        if request is None:
            return None

        if pending is not None:
            return AssistantReply(
                text=(
                    f'You already have a pending visual click on "{pending.target_query}". '
                    'Reply "confirm click" or "cancel" before staging another visual action.'
                ),
                emotion="concerned",
                should_speak=True,
            )

        if request.action == "click" and other_system_change_pending:
            return AssistantReply(
                text="You already have another pending system change. Confirm or cancel that action before staging a visual click.",
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
                text=f'I moved the pointer to the visually identified "{label}" control. I did not click it.',
                emotion="calm",
                should_speak=True,
            )

        # Strong confirmation is driven by the requested/visible control identity,
        # not by generic vision-model caution prose. Every click still requires at
        # least ordinary confirmation through click_pointer's permission boundary.
        consequential = _consequential_from_text(
            request.target,
            target.label,
            target.visible_text,
        )
        self.pending.stage(
            user_id,
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
                f'I found "{label}" and moved the pointer to its current visual location. I have not clicked anything.{caution} '
                + confirmation
            ),
            emotion="concerned",
            should_speak=True,
        )
