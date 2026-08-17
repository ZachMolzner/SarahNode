from __future__ import annotations

import asyncio

import app.agent.app_lifecycle_tools as lifecycle


def test_wait_for_app_presence_handles_just_launched_app(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_matching_pids(app: str) -> set[int]:
        assert app == "Calculator"
        calls["count"] += 1
        if calls["count"] < 3:
            return set()
        return {4242}

    def fake_visible_windows(app: str, pids: set[int]) -> list[tuple[int, str]]:
        assert app == "Calculator"
        if pids:
            return [(100, "Calculator")]
        return []

    monkeypatch.setattr(lifecycle, "_matching_pids_for_app", fake_matching_pids)
    monkeypatch.setattr(lifecycle, "_visible_windows_for_app", fake_visible_windows)

    pids, windows = asyncio.run(
        lifecycle._wait_for_app_presence(
            "Calculator",
            timeout_seconds=0.5,
            poll_seconds=0.01,
        )
    )

    assert pids == {4242}
    assert windows == [(100, "Calculator")]
    assert calls["count"] >= 3


def test_sequenced_close_waits_before_invoking_close(monkeypatch) -> None:
    events: list[str] = []

    async def fake_wait(app: str, **_kwargs):
        events.append(f"wait:{app}")
        return {1}, [(10, app)]

    async def fake_close(arguments):
        events.append(f"close:{arguments['app']}")
        return {"action": "closed", "app": arguments["app"]}

    monkeypatch.setattr(lifecycle, "_wait_for_app_presence", fake_wait)
    monkeypatch.setattr(lifecycle, "close_app_handler", fake_close)

    result = asyncio.run(lifecycle.sequenced_close_app_handler({"app": "Calculator"}))

    assert events == ["wait:Calculator", "close:Calculator"]
    assert result["action"] == "closed"


def test_sequenced_terminate_waits_before_invoking_terminate(monkeypatch) -> None:
    events: list[str] = []

    async def fake_wait(app: str, **_kwargs):
        events.append(f"wait:{app}")
        return {1}, [(10, app)]

    async def fake_terminate(arguments):
        events.append(f"terminate:{arguments['app']}")
        return {"action": "terminated", "app": arguments["app"]}

    monkeypatch.setattr(lifecycle, "_wait_for_app_presence", fake_wait)
    monkeypatch.setattr(lifecycle, "terminate_app_handler", fake_terminate)

    result = asyncio.run(lifecycle.sequenced_terminate_app_handler({"app": "Opera"}))

    assert events == ["wait:Opera", "terminate:Opera"]
    assert result["action"] == "terminated"
