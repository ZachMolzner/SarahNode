from __future__ import annotations

import asyncio

import app.services.keyboard_interaction as keyboard_module
from app.agent.contracts import ToolInvocation, ToolResult
from app.schemas.chat import ChatMessage
from app.services.keyboard_interaction import KeyboardInteractionService, parse_browser_search_request
from app.services.screen_awareness import ScreenAnalysisResult, ScreenAwarenessService, VisualTarget


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
        text="Windows accessibility found the Edge address bar.",
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


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple[ToolInvocation, bool]] = []

    async def invoke(self, invocation: ToolInvocation, *, confirmed: bool = False) -> ToolResult:
        self.calls.append((invocation, confirmed))
        if invocation.tool_name == "open_app":
            return ToolResult(ok=True, tool_name="open_app", data={"action": "launched", "app": "edge"})
        if invocation.tool_name == "replace_text_value":
            if not confirmed:
                return ToolResult(ok=False, tool_name="replace_text_value", error="requires confirmation")
            return ToolResult(ok=True, tool_name="replace_text_value", data={"replacement": True})
        if invocation.tool_name == "press_enter":
            if not confirmed:
                return ToolResult(ok=False, tool_name="press_enter", error="requires confirmation")
            return ToolResult(ok=True, tool_name="press_enter", data={"key": "enter"})
        return ToolResult(ok=False, tool_name=invocation.tool_name, error="unexpected tool")


def _screen() -> ScreenAwarenessService:
    # The workflow test monkeypatches UIA and never calls the real capture/vision client.
    return object.__new__(ScreenAwarenessService)


def test_browser_search_parser_is_narrow_and_preserves_query() -> None:
    first = parse_browser_search_request("Open Edge and search for Dexcom desktop support")
    assert first is not None
    assert first.query == "Dexcom desktop support"

    second = parse_browser_search_request('Search for "weather in Phoenix" in Microsoft Edge')
    assert second is not None
    assert second.query == "weather in Phoenix"

    assert parse_browser_search_request("Search for Dexcom") is None
    assert parse_browser_search_request("Open Chrome and search for Dexcom") is None


def test_edge_search_opens_before_confirmation_but_does_not_type_or_submit(monkeypatch) -> None:
    async def locate(_screen, _query):
        return _analysis()

    monkeypatch.setattr(keyboard_module, "locate_control_with_windows_accessibility", locate)
    tools = FakeTools()
    service = KeyboardInteractionService(screen=_screen(), tools=tools)  # type: ignore[arg-type]

    reply = asyncio.run(service.handle(_message("Open Edge and search for Dexcom desktop support")))
    assert reply is not None
    assert "confirm search" in reply.text
    assert service.has_pending("zach")
    assert [call[0].tool_name for call in tools.calls] == ["open_app"]
    assert tools.calls[0][1] is False


def test_confirm_search_revalidates_replaces_and_presses_enter_once(monkeypatch) -> None:
    async def locate(_screen, _query):
        return _analysis()

    monkeypatch.setattr(keyboard_module, "locate_control_with_windows_accessibility", locate)
    monkeypatch.setattr(
        keyboard_module,
        "window_at_point",
        lambda x, y, *, exclude_hwnd=None: (303, "New tab - Personal - Microsoft Edge"),
    )
    monkeypatch.setattr(keyboard_module, "activate_window", lambda hwnd: hwnd == 303)
    monkeypatch.setattr(keyboard_module, "remember_verified_receiver", lambda *args, **kwargs: None)

    tools = FakeTools()
    service = KeyboardInteractionService(screen=_screen(), tools=tools)  # type: ignore[arg-type]
    asyncio.run(service.handle(_message("Open Edge and search for Dexcom desktop support")))

    confirmed = asyncio.run(service.handle(_message("confirm search")))
    assert confirmed is not None
    assert "Completed the confirmed Edge search" in confirmed.text
    assert not service.has_pending("zach")

    names = [call[0].tool_name for call in tools.calls]
    assert names == ["open_app", "replace_text_value", "press_enter"]
    assert tools.calls[1][1] is True
    assert tools.calls[1][0].arguments["text"] == "Dexcom desktop support"
    assert tools.calls[2][1] is True
    assert tools.calls[2][0].arguments == {}


def test_edge_search_refuses_credential_shaped_query_before_opening_browser() -> None:
    tools = FakeTools()
    service = KeyboardInteractionService(screen=_screen(), tools=tools)  # type: ignore[arg-type]

    reply = asyncio.run(
        service.handle(_message("Open Edge and search for my password is example-do-not-use-123"))
    )
    assert reply is not None
    assert "won't submit" in reply.text
    assert tools.calls == []
    assert not service.has_pending("zach")
