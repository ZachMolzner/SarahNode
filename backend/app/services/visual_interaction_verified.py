from __future__ import annotations

import asyncio
import re

from app.agent.contracts import ToolInvocation, ToolResult
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.screen_awareness import ScreenAwarenessError, ScreenAwarenessService
from app.services.screen_change_detection import verify_visible_screen_change
from app.services.visual_grounding import locate_control_with_plain_vision
from app.services.visual_interaction import (
    VisualInteractionRequest,
    VisualInteractionService,
    _GENERIC_TARGETS,
    _MAX_SCROLL_STEPS,
    _best_target,
    _clean_literal_text,
    _clean_target,
    _physical_center,
    _sensitive_input_target,
    _target_accepts_text,
    _target_identity_matches,
)
from app.services.windows_accessibility import locate_control_with_windows_accessibility
from app.services.windows_receiver import remember_verified_receiver, window_at_point


_VERIFIED_TYPE_QUOTED_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?type\s+(?P<quote>[\"'])(?P<text>.*?)(?P=quote)\s+"
    r"(?:into|in)\s+(?:the\s+)?(?P<target>.+?)\s*$",
    re.IGNORECASE,
)
_VERIFIED_TYPE_FALLBACK_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?type\s+(?P<text>.+)\s+"
    r"(?:into|in)\s+(?:the\s+)?(?P<target>.+?)\s*$",
    re.IGNORECASE,
)


def parse_verified_type_request(text: str) -> VisualInteractionRequest | None:
    """Parse Phase 5C typing commands without splitting on words inside the literal.

    Quoted text is treated as an atomic literal block. Unquoted text uses a greedy
    text group so the final ``into``/``in`` separator is chosen instead of an earlier
    word such as the ``in`` in ``weather in Phoenix``.
    """
    raw = text.strip()
    if not raw or raw.endswith("?"):
        return None

    match = _VERIFIED_TYPE_QUOTED_RE.match(raw)
    if match is None:
        match = _VERIFIED_TYPE_FALLBACK_RE.match(raw)
    if match is None:
        return None

    literal = _clean_literal_text(match.group("text"))
    target = _clean_target(match.group("target"))
    if not literal or not target or target.lower() in _GENERIC_TARGETS:
        return None
    return VisualInteractionRequest(action="type", target=target, text=literal)


class VerifiedVisualInteractionService(VisualInteractionService):
    """Phase 5C interaction service with deterministic verification and safer UIA typing.

    Standard UIA text-entry controls are replaced through ValuePattern after confirmation,
    so existing browser URLs or field contents are not accidentally concatenated with the
    requested literal text. A successful UIA replacement also remembers the verified
    owning top-level window briefly so a following controlled key can return to that app
    after the user comes back to Sarah to type the next command. Vision-only text targets
    are refused rather than using an ambiguous append operation. Scroll verification stays
    model-free.
    """

    def can_handle(self, message: ChatMessage) -> bool:
        if parse_verified_type_request(message.content) is not None:
            return True
        return super().can_handle(message)

    async def _locate(self, target_query: str):
        if not isinstance(self.screen, ScreenAwarenessService):
            return await super()._locate(target_query)

        analysis = await locate_control_with_windows_accessibility(self.screen, target_query)
        if analysis is None:
            await asyncio.sleep(0.15)
            analysis = await locate_control_with_windows_accessibility(self.screen, target_query)
        if analysis is None:
            analysis = await locate_control_with_plain_vision(self.screen, target_query)

        target, score = _best_target(target_query, analysis.targets)
        if target is None or target.bbox_normalized is None or score < 0.55:
            detail = analysis.text.strip()
            raise ScreenAwarenessError(
                f'I can see the desktop, but I cannot locate "{target_query}" confidently enough to control the pointer.'
                + (f" Locator result: {detail}" if detail else "")
            )
        return analysis, target, score

    async def _stage_verified_type(
        self,
        message: ChatMessage,
        request: VisualInteractionRequest,
        *,
        other_system_change_pending: bool,
    ) -> AssistantReply:
        user_id = message.user_id
        pending = self.pending.get(user_id)
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

        if other_system_change_pending:
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
                'Reply "confirm type" within 2 minutes to replace the field contents with only the exact literal text you supplied, or "cancel".'
            ),
            emotion="concerned",
            should_speak=True,
        )

    async def handle(self, message: ChatMessage, *, other_system_change_pending: bool = False) -> AssistantReply | None:
        request = parse_verified_type_request(message.content)
        if request is not None:
            return await self._stage_verified_type(
                message,
                request,
                other_system_change_pending=other_system_change_pending,
            )
        return await super().handle(message, other_system_change_pending=other_system_change_pending)

    async def _execute_confirmed_type(self, pending) -> AssistantReply:
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

        if fresh_analysis.model == "windows-uia":
            x, y = _physical_center(fresh_analysis, fresh_target)
            hidden_hwnd: int | None = None
            replace_result: ToolResult | None = None
            receiver_candidate: tuple[int, str] | None = None
            try:
                hidden_hwnd = self._hide_sarah_for_input()
                if hidden_hwnd is not None:
                    await asyncio.sleep(0.25)

                # Resolve the owner from the freshly verified field coordinates while
                # Sarah is hidden. This remains valid even after the user later moves
                # their mouse back over Sarah's chat box to type a keyboard command.
                receiver_candidate = window_at_point(x, y, exclude_hwnd=hidden_hwnd)
                replace_result = await self.tools.invoke(
                    ToolInvocation(
                        tool_name="replace_text_value",
                        arguments={
                            "target_query": pending.target_query,
                            "text": pending.text,
                            "expected_x": x,
                            "expected_y": y,
                        },
                        requested_by="confirmed_uia_text_replacement_coordinator",
                    ),
                    confirmed=True,
                )
                if replace_result.ok:
                    if receiver_candidate is not None:
                        remember_verified_receiver(
                            receiver_candidate[0],
                            receiver_candidate[1],
                            source="confirmed_uia_text_field",
                            ttl_seconds=180,
                        )
                    await asyncio.sleep(0.25)
            finally:
                self._restore_sarah_after_input(hidden_hwnd)

            if replace_result is None or not replace_result.ok:
                error = replace_result.error if replace_result is not None else "The UI Automation text controller did not return a result."
                return AssistantReply(
                    text=f"I did not replace the field contents: {error or 'Windows rejected the confirmed text replacement.'}",
                    emotion="concerned",
                    should_speak=True,
                )

            label = fresh_target.visible_text or fresh_target.label or pending.target_query
            return AssistantReply(
                text=(
                    f'Replaced the current contents of "{label}" with the exact requested literal text after re-verifying the field. '
                    "I did not press Enter, Tab, or any shortcut. Windows UI Automation accepted the replacement and retained the verified app receiver for a short continuation."
                ),
                emotion="calm",
                should_speak=True,
            )

        return AssistantReply(
            text=(
                f'I found "{fresh_target.visible_text or fresh_target.label or pending.target_query}" visually, but Windows does not expose '
                "a replaceable text value for it. I did not type because that could append to or corrupt existing contents."
            ),
            emotion="concerned",
            should_speak=True,
        )

    async def _execute_scroll(self, direction: str, steps: int) -> AssistantReply:
        if not isinstance(self.screen, ScreenAwarenessService):
            return await super()._execute_scroll(direction, steps)

        if steps < 1 or steps > _MAX_SCROLL_STEPS:
            return AssistantReply(
                text=f"A single scroll request is limited to 1-{_MAX_SCROLL_STEPS} steps.",
                emotion="concerned",
                should_speak=True,
            )

        try:
            before = await self.screen._capture()
        except Exception:
            before = None

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

        verification = "The bounded wheel input was accepted by Windows."
        if before is not None:
            try:
                change = await verify_visible_screen_change(self.screen, before.data_url)
                if change.changed:
                    verification = "The visible content changed after the scroll."
                else:
                    verification = (
                        "No clear visible content change was detected. The page may already be at an edge, "
                        "or the area under the pointer may not be scrollable."
                    )
            except Exception:
                verification = "The bounded wheel input was accepted by Windows, but the local before/after comparison was unavailable."

        return AssistantReply(
            text=(
                f"Scrolled {direction} {steps} bounded step{'s' if steps != 1 else ''}. "
                f"Verification: {verification}"
            ),
            emotion="calm",
            should_speak=True,
        )
