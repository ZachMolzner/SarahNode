from __future__ import annotations

import asyncio

from app.agent.contracts import ToolInvocation, ToolResult
from app.schemas.chat import AssistantReply
from app.services.screen_awareness import ScreenAwarenessService
from app.services.screen_change_detection import verify_visible_screen_change
from app.services.visual_interaction import VisualInteractionService, _MAX_SCROLL_STEPS


class VerifiedVisualInteractionService(VisualInteractionService):
    """Phase 5C interaction service with model-free scroll verification.

    Click and typing behavior stays in the accepted base implementation. Scroll
    verification uses before/after screenshots so a local vision-model empty response
    cannot turn an otherwise successful wheel action into a verification failure.
    """

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
