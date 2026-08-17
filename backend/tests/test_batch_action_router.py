from __future__ import annotations

from pathlib import Path

import pytest

import app.agent.confirmed_action_tools as action_tools
from app.agent.batch_action_router import PendingActionPlanStore, parse_action_plan, split_action_commands


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("Desktop", "Downloads", "Documents", "Pictures", "Music", "Videos", "SarahNode", "AppData"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(action_tools, "_home", lambda: tmp_path.resolve())
    return tmp_path


def test_split_three_safe_actions() -> None:
    assert split_action_commands("Open Opera, open Downloads, and bring VS Code to the front") == [
        "Open Opera",
        "open Downloads",
        "bring VS Code to the front",
    ]


def test_splitter_does_not_break_action_words_inside_quotes() -> None:
    segments = split_action_commands(
        'Create file note.txt in Downloads with text "open Opera and close Steam", then open Downloads'
    )
    assert segments == [
        'Create file note.txt in Downloads with text "open Opera and close Steam"',
        "open Downloads",
    ]


def test_safe_only_plan_runs_without_confirmation() -> None:
    plan = parse_action_plan("Open Opera and open Downloads")
    assert plan is not None
    assert len(plan.actions) == 2
    assert not plan.requires_confirmation
    assert [action.tool_name for action in plan.actions] == ["open_app", "open_path"]


def test_shared_open_verb_expands_multiple_targets() -> None:
    plan = parse_action_plan("Open Opera, Calculator, and Downloads")
    assert plan is not None
    assert len(plan.actions) == 3
    assert not plan.requires_confirmation
    assert [action.tool_name for action in plan.actions] == ["open_app", "open_app", "open_path"]


def test_shared_close_verb_requires_one_confirmation() -> None:
    plan = parse_action_plan("Close Calculator and Opera")
    assert plan is not None
    assert len(plan.actions) == 2
    assert plan.requires_confirmation
    assert [action.tool_name for action in plan.actions] == ["close_app", "close_app"]


def test_filename_with_and_is_not_misread_as_batch() -> None:
    assert parse_action_plan("Open Research and Development.docx") is None


def test_mixed_plan_requires_one_confirmation(fake_home: Path) -> None:
    plan = parse_action_plan("Create folder BatchTest in Downloads, then open Opera")
    assert plan is not None
    assert len(plan.actions) == 2
    assert plan.requires_confirmation
    assert plan.actions[0].tool_name == "create_folder"
    assert plan.actions[1].tool_name == "open_app"
    assert not (fake_home / "Downloads" / "BatchTest").exists()


def test_force_close_inside_batch_requires_confirmation() -> None:
    plan = parse_action_plan("Open Opera and kill Opera")
    assert plan is not None
    assert plan.requires_confirmation
    assert [action.tool_name for action in plan.actions] == ["open_app", "terminate_app"]


def test_unrecognized_step_rejects_entire_batch() -> None:
    with pytest.raises(ValueError):
        parse_action_plan("Open Opera and dance around")


def test_batch_size_is_limited() -> None:
    request = "; ".join(["Open Opera"] * 9)
    with pytest.raises(ValueError):
        parse_action_plan(request)


def test_pending_plans_are_isolated_by_user() -> None:
    plan = parse_action_plan("Open Opera and open Downloads")
    assert plan is not None

    store = PendingActionPlanStore(ttl_seconds=180)
    store.stage("user-a", plan)
    assert store.get("user-a") is not None
    assert store.get("user-b") is None
