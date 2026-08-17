from __future__ import annotations

from pathlib import Path

import pytest

import app.agent.confirmed_action_tools as action_tools
from app.agent.confirmed_action_router import (
    ConfirmedActionRequest,
    PendingConfirmedActionStore,
    is_cancellation,
    is_confirmation,
    parse_confirmed_action,
)
from app.agent.confirmed_action_tools import (
    _process_names_for_app,
    confirmed_action_tools,
    resolve_existing_mutation_path,
)
from app.agent.contracts import PermissionScope
from app.agent.permissions import PermissionDenied, default_policy


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("Desktop", "Downloads", "Documents", "Pictures", "Music", "Videos", "SarahNode", "AppData"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(action_tools, "_home", lambda: tmp_path.resolve())
    return tmp_path


def test_confirm_and_cancel_words_are_explicit() -> None:
    assert is_confirmation("confirm")
    assert is_confirmation("yes, confirm")
    assert is_confirmation("go ahead")
    assert is_cancellation("cancel")
    assert is_cancellation("never mind")
    assert not is_confirmation("maybe")


def test_pending_actions_are_isolated_by_user() -> None:
    store = PendingConfirmedActionStore(ttl_seconds=180)
    request = ConfirmedActionRequest("close_app", {"app": "Opera"}, "close Opera")
    store.stage("user-a", request)

    assert store.get("user-a") is not None
    assert store.get("user-b") is None
    assert store.cancel("user-b") is None
    assert store.get("user-a") is not None


def test_create_folder_is_staged_with_exact_path(fake_home: Path) -> None:
    request = parse_confirmed_action("Create folder TestFolder in Downloads")
    assert request is not None
    assert request.tool_name == "create_folder"
    assert request.arguments["path"] == str((fake_home / "Downloads" / "TestFolder").resolve())
    assert not (fake_home / "Downloads" / "TestFolder").exists()


def test_create_file_with_content_is_staged_without_writing(fake_home: Path) -> None:
    request = parse_confirmed_action('Create file note.txt in Downloads with text "hello world"')
    assert request is not None
    assert request.tool_name == "create_file"
    assert request.arguments["path"] == str((fake_home / "Downloads" / "note.txt").resolve())
    assert request.arguments["content"] == "hello world"
    assert not (fake_home / "Downloads" / "note.txt").exists()


def test_rename_and_move_are_previewed_only(fake_home: Path) -> None:
    source = fake_home / "Downloads" / "old.txt"
    source.write_text("test", encoding="utf-8")

    rename = parse_confirmed_action("Rename old.txt to new.txt")
    assert rename is not None
    assert rename.tool_name == "move_path"
    assert rename.arguments["source"] == str(source.resolve())
    assert rename.arguments["destination"] == str((source.parent / "new.txt").resolve())
    assert source.exists()

    move = parse_confirmed_action("Move old.txt to Documents")
    assert move is not None
    assert move.arguments["destination"] == str((fake_home / "Documents" / "old.txt").resolve())
    assert source.exists()


def test_delete_routes_to_recycle_bin_action(fake_home: Path) -> None:
    disposable = fake_home / "Downloads" / "disposable.txt"
    disposable.write_text("test", encoding="utf-8")

    request = parse_confirmed_action("Delete disposable.txt")
    assert request is not None
    assert request.tool_name == "recycle_path"
    assert request.arguments["path"] == str(disposable.resolve())
    assert "Recycle Bin" in request.summary
    assert disposable.exists()


def test_close_app_requires_confirmation_request() -> None:
    request = parse_confirmed_action("Close Opera")
    assert request is not None
    assert request.tool_name == "close_app"
    assert request.arguments == {"app": "Opera"}


def test_force_close_is_a_distinct_high_risk_request() -> None:
    request = parse_confirmed_action("Kill Opera")
    assert request is not None
    assert request.tool_name == "terminate_app"
    assert request.arguments == {"app": "Opera"}
    assert "force-close" in request.summary

    request = parse_confirmed_action("Force close VS Code")
    assert request is not None
    assert request.tool_name == "terminate_app"


def test_force_close_file_explorer_is_blocked() -> None:
    with pytest.raises(ValueError):
        parse_confirmed_action("Kill File Explorer")


def test_calculator_uses_packaged_process_alias() -> None:
    names = {name.lower() for name in _process_names_for_app("Calculator")}
    assert "calculatorapp.exe" in names
    assert "calc.exe" in names


def test_generic_or_unsupported_requests_are_not_auto_staged(fake_home: Path) -> None:
    assert parse_confirmed_action("Delete a file") is None
    assert parse_confirmed_action("Install Discord") is None
    assert parse_confirmed_action("Run PowerShell as administrator") is None


def test_top_level_profile_folders_and_sarahnode_are_protected(fake_home: Path) -> None:
    with pytest.raises(ValueError):
        resolve_existing_mutation_path("Downloads")

    protected_file = fake_home / "SarahNode" / "important.txt"
    protected_file.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_existing_mutation_path(str(protected_file))


def test_phase4c_tools_require_confirmed_invocation() -> None:
    policy = default_policy()

    for tool in confirmed_action_tools():
        assert tool.requires_confirmation
        with pytest.raises(PermissionDenied):
            policy.authorize(tool, confirmed=False)
        policy.authorize(tool, confirmed=True)


def test_default_policy_uses_granular_scopes_not_broad_control() -> None:
    policy = default_policy()

    assert PermissionScope.FILES_CREATE in policy.granted_scopes
    assert PermissionScope.FILES_MOVE in policy.granted_scopes
    assert PermissionScope.FILES_RECYCLE in policy.granted_scopes
    assert PermissionScope.APPS_CLOSE in policy.granted_scopes
    assert PermissionScope.APPS_TERMINATE in policy.granted_scopes

    assert PermissionScope.FILES_WRITE not in policy.granted_scopes
    assert PermissionScope.DESKTOP_CONTROL not in policy.granted_scopes
    assert PermissionScope.SYSTEM_CONTROL not in policy.granted_scopes
