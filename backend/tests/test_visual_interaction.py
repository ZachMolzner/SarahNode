from __future__ import annotations

import asyncio

import pytest

from app.agent.contracts import ToolInvocation, ToolResult
from app.agent.permissions import default_policy
from app.agent.pointer_tools import pointer_tools
from app.agent.tool_registry import ToolRegistry
from app.schemas.chat import ChatMessage
from app.services.screen_awareness import ScreenAnalysisResult, VisualTarget
from app.services.visual_interaction import (
    VisualInteractionService,
    _consequential_from_text,
    _physical_center,
    parse_visual_interaction_request,
)


def _analysis(
    *,
    text: str = "Visible target found.",
    targets: tuple[VisualTarget, ...] = (),
    left: int = 0,
    top: int = 0,
    width: int = 1920,
    height: int = 1080,
) -> ScreenAnalysisResult:
    return ScreenAnalysisResult(
        text=text,
        model="test-vision",
        reasoning_mode="locate",
        source_width=width,
        source_height=height,
        sent_width=width,
        sent_height=height,
        capture_left=left,
        capture_top=top,
        capture_width=width,
        capture_height=height,
        sarah_hidden_for_capture=False,
        targets=targets,
        recommended_steps=(),
        caution=None,
    )


def _target(
    label: str = "Not now",
    *,
    bbox: tuple[int, int, int, int] = (700, 100, 900, 200),
    confidence: float = 0.95,
    role: str = "button",
) -> VisualTarget:
    return VisualTarget(
        label=label,
        role=role,
        visible_text=label,
        bbox_normalized=bbox,
        confidence=confidence,
    )


def _message(content: str) -> ChatMessage:
    return ChatMessage(user_id="zach", username="zach", content=content)


def test_visual_action_parser_distinguishes_commands_from_guidance() -> None:
    assert parse_visual_interaction_request("Which button should I click to continue?") is None
    assert parse_visual_interaction_request("What should I click next?") is None

    click = parse_visual_interaction_request("Click the 'Not now' button")
    assert click is not None
    assert click.action == "click"
    assert click.target == "Not now"

    move = parse_visual_interaction_request("Move cursor to the search box")
    assert move is not None
    assert move.action == "move"
    assert move.target == "search box"

    typed = parse_visual_interaction_request('Type "hello from Sarah" into Address and search bar')
    assert typed is not None
    assert typed.action == "type"
    assert typed.target == "Address and search bar"
    assert typed.text == "hello from Sarah"

    scroll = parse_visual_interaction_request("Scroll down 2 steps")
    assert scroll is not None
    assert scroll.action == "scroll"
    assert scroll.direction == "down"
    assert scroll.steps == 2


def test_visual_target_center_maps_normalized_bbox_to_virtual_screen() -> None:
    analysis = _analysis(left=-1920, top=0, width=1920, height=1080)
    target = _target(bbox=(400, 400, 600, 600))
    assert _physical_center(analysis, target) == (-960, 540)


def test_consequential_classifier_uses_control_identity_not_generic_caution() -> None:
    assert _consequential_from_text("Delete account")
    assert _consequential_from_text("Install")
    assert _consequential_from_text("Submit")
    assert not _consequential_from_text("Not now")
    assert not _consequential_from_text("Continue")


class FakeScreen:
    def __init__(self, analyses: list[ScreenAnalysisResult]) -> None:
        self.analyses = analyses
        self.questions: list[str] = []

    async def analyze(self, question: str) -> ScreenAnalysisResult:
        self.questions.append(question)
        if not self.analyses:
            raise AssertionError("No fake screen analysis left")
        return self.analyses.pop(0)


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple[ToolInvocation, bool]] = []

    async def invoke(self, invocation: ToolInvocation, *, confirmed: bool = False) -> ToolResult:
        self.calls.append((invocation, confirmed))
        if invocation.tool_name == "move_pointer":
            return ToolResult(ok=True, tool_name="move_pointer", data={"action": "pointer_moved"})
        if invocation.tool_name == "click_pointer":
            if not confirmed:
                return ToolResult(ok=False, tool_name="click_pointer", error="requires confirmation")
            return ToolResult(ok=True, tool_name="click_pointer", data={"action": "left_clicked"})
        if invocation.tool_name == "type_text":
            if not confirmed:
                return ToolResult(ok=False, tool_name="type_text", error="requires confirmation")
            return ToolResult(ok=True, tool_name="type_text", data={"action": "literal_text_typed"})
        if invocation.tool_name == "scroll_pointer":
            return ToolResult(ok=True, tool_name="scroll_pointer", data={"action": "wheel_scrolled"})
        return ToolResult(ok=False, tool_name=invocation.tool_name, error="unexpected tool")


def test_visual_click_stages_then_revalidates_and_verifies() -> None:
    initial = _analysis(targets=(_target(),))
    fresh = _analysis(targets=(_target(bbox=(710, 110, 910, 210)),))
    verification = _analysis(text="The notification prompt is no longer visible.")
    screen = FakeScreen([initial, fresh, verification])
    tools = FakeTools()
    service = VisualInteractionService(screen=screen, tools=tools)  # type: ignore[arg-type]

    staged = asyncio.run(service.handle(_message("Click the Not now button")))
    assert staged is not None
    assert "I have not clicked anything" in staged.text
    assert "confirm click" in staged.text
    assert service.has_pending("zach")
    assert [call[0].tool_name for call in tools.calls] == ["move_pointer"]

    confirmed = asyncio.run(service.handle(_message("confirm click")))
    assert confirmed is not None
    assert "Clicked" in confirmed.text
    assert "notification prompt is no longer visible" in confirmed.text
    assert not service.has_pending("zach")
    assert [call[0].tool_name for call in tools.calls] == ["move_pointer", "click_pointer"]
    assert tools.calls[-1][1] is True
    assert len(screen.questions) == 3


def test_consequential_visual_click_requires_stronger_confirmation() -> None:
    screen = FakeScreen([_analysis(targets=(_target("Delete"),))])
    tools = FakeTools()
    service = VisualInteractionService(screen=screen, tools=tools)  # type: ignore[arg-type]

    staged = asyncio.run(service.handle(_message("Click Delete")))
    assert staged is not None
    assert "confirm consequential click" in staged.text

    weak = asyncio.run(service.handle(_message("confirm click")))
    assert weak is not None
    assert "confirm consequential click" in weak.text
    assert service.has_pending("zach")
    assert [call[0].tool_name for call in tools.calls] == ["move_pointer"]


def test_literal_typing_stages_and_requires_matching_confirmation() -> None:
    initial = _analysis(targets=(_target("Address and search bar", role="Edit"),))
    fresh = _analysis(targets=(_target("Address and search bar", role="Edit", bbox=(100, 50, 900, 110)),))
    verification = _analysis(text="The address field visibly changed.")
    screen = FakeScreen([initial, fresh, verification])
    tools = FakeTools()
    service = VisualInteractionService(screen=screen, tools=tools)  # type: ignore[arg-type]

    staged = asyncio.run(service.handle(_message('Type "hello from Sarah" into Address and search bar')))
    assert staged is not None
    assert "I have not focused the field or typed anything" in staged.text
    assert "confirm type" in staged.text
    assert [call[0].tool_name for call in tools.calls] == ["move_pointer"]

    wrong = asyncio.run(service.handle(_message("confirm click")))
    assert wrong is not None
    assert "confirm type" in wrong.text
    assert service.has_pending("zach")
    assert [call[0].tool_name for call in tools.calls] == ["move_pointer"]

    confirmed = asyncio.run(service.handle(_message("confirm type")))
    assert confirmed is not None
    assert "Typed the exact requested literal text" in confirmed.text
    assert "did not press Enter" in confirmed.text
    assert not service.has_pending("zach")
    assert [call[0].tool_name for call in tools.calls] == ["move_pointer", "click_pointer", "type_text"]
    assert tools.calls[-2][1] is True
    assert tools.calls[-1][1] is True
    assert tools.calls[-1][0].arguments["text"] == "hello from Sarah"


def test_sensitive_field_typing_is_blocked_before_input() -> None:
    screen = FakeScreen([_analysis(targets=(_target("Password", role="PasswordEdit"),))])
    tools = FakeTools()
    service = VisualInteractionService(screen=screen, tools=tools)  # type: ignore[arg-type]

    reply = asyncio.run(service.handle(_message('Type "secret" into Password')))
    assert reply is not None
    assert "will not type" in reply.text
    assert not service.has_pending("zach")
    assert [call[0].tool_name for call in tools.calls] == ["move_pointer"]


def test_bounded_scroll_runs_without_confirmation_and_verifies() -> None:
    screen = FakeScreen([_analysis(text="The page moved downward.")])
    tools = FakeTools()
    service = VisualInteractionService(screen=screen, tools=tools)  # type: ignore[arg-type]

    reply = asyncio.run(service.handle(_message("Scroll down 2 steps")))
    assert reply is not None
    assert "Scrolled down 2 bounded steps" in reply.text
    assert [call[0].tool_name for call in tools.calls] == ["scroll_pointer"]
    assert tools.calls[0][1] is False
    assert tools.calls[0][0].arguments == {"direction": "down", "steps": 2}


def test_scroll_over_limit_is_rejected_before_tool_call() -> None:
    screen = FakeScreen([])
    tools = FakeTools()
    service = VisualInteractionService(screen=screen, tools=tools)  # type: ignore[arg-type]

    reply = asyncio.run(service.handle(_message("Scroll down 9 steps")))
    assert reply is not None
    assert "limited to 1-5 steps" in reply.text
    assert tools.calls == []


def test_intervening_visual_pending_can_be_cancelled_without_input() -> None:
    screen = FakeScreen([_analysis(targets=(_target(),))])
    tools = FakeTools()
    service = VisualInteractionService(screen=screen, tools=tools)  # type: ignore[arg-type]

    asyncio.run(service.handle(_message("Click Not now")))
    cancelled = service.cancel_pending("zach")
    assert cancelled is not None
    assert cancelled.target_query == "Not now"
    assert not service.has_pending("zach")
    assert all(call[0].tool_name not in {"click_pointer", "type_text"} for call in tools.calls)


def test_input_tools_are_internal_and_mutating_input_requires_confirmation() -> None:
    registry = ToolRegistry(default_policy())
    registry.register_many(pointer_tools())

    assert registry.list_tools() == []
    internal_names = {tool.name for tool in registry.list_tools(include_internal=True)}
    assert internal_names == {"move_pointer", "click_pointer", "type_text", "scroll_pointer"}

    click = asyncio.run(
        registry.invoke(ToolInvocation(tool_name="click_pointer", arguments={"x": 0, "y": 0}))
    )
    assert not click.ok
    assert "requires user confirmation" in (click.error or "")

    typed = asyncio.run(
        registry.invoke(ToolInvocation(tool_name="type_text", arguments={"text": "hello"}))
    )
    assert not typed.ok
    assert "requires user confirmation" in (typed.error or "")
