from __future__ import annotations

import asyncio
from typing import Any, Mapping

from app.agent.confirmed_action_tools import (
    _matching_pids_for_app,
    _visible_windows_for_app,
    close_app_handler,
    terminate_app_handler,
)
from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition


async def _wait_for_app_presence(
    app: str,
    *,
    timeout_seconds: float = 2.5,
    poll_seconds: float = 0.1,
) -> tuple[set[int], list[tuple[int, str]]]:
    """Wait briefly for a just-launched app to become observable.

    Windows app launch is asynchronous. A command plan such as "open Calculator,
    then close Calculator" can reach the close step before CalculatorApp.exe or its
    visible window is registered. Polling only when the target is initially absent
    preserves fast behavior for already-running apps while making dependent batch
    steps reliable.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, timeout_seconds)

    while True:
        pids = _matching_pids_for_app(app)
        windows = _visible_windows_for_app(app, pids)
        if pids or windows:
            return pids, windows
        if loop.time() >= deadline:
            return pids, windows
        await asyncio.sleep(max(0.05, poll_seconds))


async def sequenced_close_app_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    app = str(arguments.get("app", "")).strip()
    if app:
        await _wait_for_app_presence(app)
    return await close_app_handler(arguments)


async def sequenced_terminate_app_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    app = str(arguments.get("app", "")).strip()
    if app:
        await _wait_for_app_presence(app)
    return await terminate_app_handler(arguments)


def hardened_close_app_tool() -> ToolDefinition:
    return ToolDefinition(
        name="close_app",
        description=(
            "Close all visible windows of one supported app using the normal Windows close path and verify the windows disappear. "
            "If the app was just launched, wait briefly for its process/window to appear before closing it. "
            "Does not force-terminate processes. Requires explicit confirmation."
        ),
        handler=sequenced_close_app_handler,
        parameters={
            "type": "object",
            "properties": {"app": {"type": "string"}},
            "required": ["app"],
            "additionalProperties": False,
        },
        scopes=frozenset({PermissionScope.APPS_CLOSE}),
        risk=RiskLevel.MEDIUM,
        requires_confirmation=True,
    )


def hardened_terminate_app_tool() -> ToolDefinition:
    return ToolDefinition(
        name="terminate_app",
        description=(
            "Force-close all matching processes for one supported app after an explicit kill/terminate/force-close request. "
            "If the app was just launched, wait briefly for its process/window to appear before terminating it. "
            "This can discard unsaved work. Requires explicit confirmation."
        ),
        handler=sequenced_terminate_app_handler,
        parameters={
            "type": "object",
            "properties": {"app": {"type": "string"}},
            "required": ["app"],
            "additionalProperties": False,
        },
        scopes=frozenset({PermissionScope.APPS_TERMINATE}),
        risk=RiskLevel.HIGH,
        requires_confirmation=True,
    )
