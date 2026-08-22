from __future__ import annotations

import asyncio

from app.agent.contracts import ToolInvocation, ToolResult
from app.schemas.chat import AssistantReply
from app.services.screen_awareness import ScreenAwarenessError, ScreenAwarenessService
from app.services.screen_change_detection import verify_visible_screen_change
from app.services.visual_grounding import locate_control_with_plain_vision
from app.services.visual_interaction import (
    VisualInteractionService,
    _MAX_SCROLL_STEPS,
    _best_target,
    _physical_center,
    _sensitive_input_target,
    _target_accepts_text,
    _target_identity_matches,
)
from app.services.windows_accessibility import locate_control_with_windows_accessibility


class VerifiedVisualInteractionService(VisualInteractionService):
    """Phase 5C interaction service with deterministic verification and safer UIA typing.

    Standard UIA text-entry controls are replaced through ValuePattern after confirmation,
    so existing browser URLs or field contents are not accidentally concatenated with the
    requested literal text. Vision-only text targets are refused rather than using an
    ambiguous append operation. Scroll verification stays model-free.
    """

    async def _locate(self, target_query: str):
        if not isinstance(self.screen, ScreenAwarenessService):
            return await super()._locate(target_query)

        # UIA is deterministic and already proved reliable on this Windows machine.
        # Give transient browser accessibility-tree updates one short retry before
        # falling back to local vision grounding.
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

        # For standard Windows-accessible fields, replace the current value exactly.
        # This prevents address-bar text from being inserted into an existing URL.
        if fresh_analysis.model == "windows-uia":
            x, y = _physical_center(fresh_analysis, fresh_target)
            hidden_hwnd: int | None = None
            replace_result: ToolResult | None = None
            try:
                hidden_hwnd = self._hide_sarah_for_input()
                if hidden_hwnd is not None:
                    await asyncio.sleep(0.25)
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
                    "I did not press Enter, Tab, or any shortcut. Windows UI Automation accepted the replacement."
                ),
                emotion="calm",
                should_speak=True,
            )

        # A vision-only bounding box cannot tell us whether an existing value is selected,
        # so do not risk concatenating the new text with unknown existing contents.
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
