from __future__ import annotations

import asyncio

import app.services.visual_interaction_verified as verified_module
from app.agent.contracts import ToolInvocation, ToolResult
from app.schemas.chat import ChatMessage
from app.services.screen_awareness import ScreenAnalysisResult, VisualTarget
from app.services.visual_interaction_verified import VerifiedVisualInteractionService


def _message(content: str) -> ChatMessage:
    return ChatMessage(user_id="zach", username="zach", content=content)


def _analysis() -> ScreenAnalysisResult:
    target = VisualTarget(
        label="Address and search bar",
        role="Edit",
        visible_text="Address and search bar",
        bbox_normalized=(100, 20, 900, 80),
        confidence=0.99,
    )
    return ScreenAnalysisResult(
        text='Windows accessibility identified "Address and search bar" as a visible Edit.',
        model="windows-uia",
        reasoning_mode="locate",
        source_width=1920,
        source_height=1080,
        sent_width=1920,
        sent_height=1080,
        capture_left=0,
        capture_top=0,
        capture_width=1920,
        capture_height=1080,
        sarah_hidden_for_capture=False,
        targets=(target,),
        recommended_steps=(),
        caution=None,
    )


class FakeScreen:
    def __init__(self) -> None:
        self.analyses = [_analysis(), _analysis()]

    async def analyze(self, _question: str) -> ScreenAnalysisResult:
        return self.analyses.pop(0)


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple[ToolInvocation, bool]] = []

    async def invoke(self, invocation: ToolInvocation, *, confirmed: bool = False) -> ToolResult:
        self.calls.append((invocation, confirmed))
        if invocation.tool_name == "move_pointer":
            return ToolResult(ok=True, tool_name="move_pointer", data={"action": "pointer_moved"})
        if invocation.tool_name == "replace_text_value":
            if not confirmed:
                return ToolResult(ok=False, tool_name="replace_text_value", error="requires confirmation")
            return ToolResult(
                ok=True,
                tool_name="replace_text_value",
                data={"action": "uia_text_replaced", "replacement": True},
            )
        return ToolResult(ok=False, tool_name=invocation.tool_name, error="unexpected tool")


def test_confirmed_uia_typing_replaces_current_contents_and_remembers_receiver(monkeypatch) -> None:
    screen = FakeScreen()
    tools = FakeTools()
    remembered: list[tuple[int, str, str]] = []

    monkeypatch.setattr(
        verified_module,
        "window_at_point",
        lambda x, y, *, exclude_hwnd=None: (303, "Microsoft Edge"),
    )

    def remember(hwnd, title, *, source="visual_interaction", ttl_seconds=180):
        remembered.append((hwnd, title, source))
        return object()

    monkeypatch.setattr(verified_module, "remember_verified_receiver", remember)

    service = VerifiedVisualInteractionService(screen=screen, tools=tools)  # type: ignore[arg-type]

    staged = asyncio.run(service.handle(_message('Type "weather in Phoenix" into Address and search bar')))
    assert staged is not None
    assert "confirm type" in staged.text
    assert [call[0].tool_name for call in tools.calls] == ["move_pointer"]

    confirmed = asyncio.run(service.handle(_message("confirm type")))
    assert confirmed is not None
    assert "Replaced the current contents" in confirmed.text
    names = [call[0].tool_name for call in tools.calls]
    assert names == ["move_pointer", "replace_text_value"]
    replacement_call = tools.calls[-1]
    assert replacement_call[1] is True
    assert replacement_call[0].arguments["text"] == "weather in Phoenix"
    assert "click_pointer" not in names
    assert "type_text" not in names
    assert remembered == [(303, "Microsoft Edge", "confirmed_uia_text_field")]
