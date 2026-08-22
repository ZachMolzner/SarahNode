from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.agent.contracts import ToolInvocation, ToolResult
from app.agent.keyboard_tools import keyboard_tools
from app.agent.permissions import default_policy
from app.agent.tool_registry import ToolRegistry
from app.schemas.chat import ChatMessage
from app.services.keyboard_interaction import KeyboardInteractionService, WindowContext, parse_keyboard_request


_DATA_URL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zkz8AAAAASUVORK5CYII="


@dataclass
class FakeFrame:
    data_url: str = _DATA_URL


class FakeScreen:
    def __init__(self) -> None:
        self.hide_count = 0
        self.restore_count = 0
        self.capture_count = 0

    def _hide_sarah_if_foreground(self) -> int:
        self.hide_count += 1
        return 999

    def _restore_sarah_window(self, hwnd: int | None) -> None:
        assert hwnd == 999
        self.restore_count += 1

    async def _capture(self) -> FakeFrame:
        self.capture_count += 1
        return FakeFrame()


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple[ToolInvocation, bool]] = []

    async def invoke(self, invocation: ToolInvocation, *, confirmed: bool = False) -> ToolResult:
        self.calls.append((invocation, confirmed))
        if invocation.tool_name == "press_safe_key":
            return ToolResult(ok=True, tool_name="press_safe_key", data={"key": invocation.arguments.get("key")})
        if invocation.tool_name == "press_enter":
            if not confirmed:
                return ToolResult(ok=False, tool_name="press_enter", error="requires confirmation")
            return ToolResult(ok=True, tool_name="press_enter", data={"key": "enter"})
        return ToolResult(ok=False, tool_name=invocation.tool_name, error="unexpected tool")


def _message(content: str) -> ChatMessage:
    return ChatMessage(user_id="zach", username="zach", content=content)


def _provider(*contexts: WindowContext):
    values = iter(contexts)
    return lambda: next(values)


def _underlying_provider(*contexts: WindowContext):
    values = iter(contexts)
    return lambda _sarah_hwnd: next(values)


def _activator(_context: WindowContext) -> bool:
    return True


def test_keyboard_parser_allows_only_named_single_keys() -> None:
    expected = {
        "Press Enter": "enter",
        "Hit Return": "enter",
        "Press Escape": "escape",
        "Press Esc": "escape",
        "Press Tab": "tab",
        "Press Backspace": "backspace",
        "Press Arrow Up": "arrow_up",
        "Press Up Arrow": "arrow_up",
        "Press Arrow Down": "arrow_down",
        "Press Down Arrow": "arrow_down",
    }
    for text, key in expected.items():
        request = parse_keyboard_request(text)
        assert request is not None
        assert request.key == key

    assert parse_keyboard_request("Press Ctrl+C") is None
    assert parse_keyboard_request("Press F5") is None
    assert parse_keyboard_request("Press A") is None
    assert parse_keyboard_request("Hold Enter") is None
    assert parse_keyboard_request("Press Enter 5 times") is None


def test_enter_stages_then_requires_confirmation_and_fresh_window() -> None:
    screen = FakeScreen()
    tools = FakeTools()
    context = WindowContext(hwnd=101, title="Microsoft Edge")
    service = KeyboardInteractionService(
        screen=screen,  # type: ignore[arg-type]
        tools=tools,  # type: ignore[arg-type]
        context_provider=_provider(context, context),
        underlying_provider=_underlying_provider(context, context),
        activator=_activator,
    )

    staged = asyncio.run(service.handle(_message("Press Enter")))
    assert staged is not None
    assert "Microsoft Edge" in staged.text
    assert "confirm enter" in staged.text
    assert service.has_pending("zach")
    assert tools.calls == []

    confirmed = asyncio.run(service.handle(_message("confirm enter")))
    assert confirmed is not None
    assert "Microsoft Edge" in confirmed.text
    assert "Pressed Enter once" in confirmed.text
    assert not service.has_pending("zach")
    assert len(tools.calls) == 1
    assert tools.calls[0][0].tool_name == "press_enter"
    assert tools.calls[0][1] is True


def test_enter_refuses_when_receiving_window_changes() -> None:
    screen = FakeScreen()
    tools = FakeTools()
    edge = WindowContext(hwnd=101, title="Microsoft Edge")
    notepad = WindowContext(hwnd=202, title="Notepad")
    service = KeyboardInteractionService(
        screen=screen,  # type: ignore[arg-type]
        tools=tools,  # type: ignore[arg-type]
        context_provider=_provider(edge, notepad),
        underlying_provider=_underlying_provider(edge, notepad),
        activator=_activator,
    )

    asyncio.run(service.handle(_message("Press Enter")))
    refused = asyncio.run(service.handle(_message("confirm enter")))
    assert refused is not None
    assert "receiving window changed" in refused.text
    assert "Microsoft Edge" in refused.text
    assert "Notepad" in refused.text
    assert tools.calls == []
    assert not service.has_pending("zach")


def test_safe_key_activates_underlying_window_and_executes_once() -> None:
    screen = FakeScreen()
    tools = FakeTools()
    edge = WindowContext(hwnd=303, title="Microsoft Edge")
    activated: list[WindowContext] = []
    service = KeyboardInteractionService(
        screen=screen,  # type: ignore[arg-type]
        tools=tools,  # type: ignore[arg-type]
        context_provider=_provider(edge),
        underlying_provider=_underlying_provider(edge),
        activator=lambda context: activated.append(context) is None,
    )

    reply = asyncio.run(service.handle(_message("Press Arrow Down")))
    assert reply is not None
    assert 'Pressed Arrow Down once in "Microsoft Edge"' in reply.text
    assert activated == [edge]
    assert len(tools.calls) == 1
    invocation, confirmed = tools.calls[0]
    assert invocation.tool_name == "press_safe_key"
    assert invocation.arguments == {"key": "arrow_down"}
    assert confirmed is False


def test_safe_key_refuses_if_underlying_window_cannot_be_activated() -> None:
    screen = FakeScreen()
    tools = FakeTools()
    edge = WindowContext(hwnd=404, title="Microsoft Edge")
    service = KeyboardInteractionService(
        screen=screen,  # type: ignore[arg-type]
        tools=tools,  # type: ignore[arg-type]
        context_provider=_provider(edge),
        underlying_provider=_underlying_provider(edge),
        activator=lambda _context: False,
    )

    reply = asyncio.run(service.handle(_message("Press Backspace")))
    assert reply is not None
    assert "could not safely activate and verify" in reply.text
    assert tools.calls == []


def test_keyboard_tools_are_model_hidden_and_enter_requires_confirmation() -> None:
    registry = ToolRegistry(default_policy())
    registry.register_many(keyboard_tools())

    assert registry.list_tools() == []
    internal = {tool.name: tool for tool in registry.list_tools(include_internal=True)}
    assert set(internal) == {"press_safe_key", "press_enter"}
    assert internal["press_safe_key"].model_visible is False
    assert internal["press_enter"].model_visible is False

    result = asyncio.run(registry.invoke(ToolInvocation(tool_name="press_enter", arguments={})))
    assert not result.ok
    assert "requires user confirmation" in (result.error or "")
