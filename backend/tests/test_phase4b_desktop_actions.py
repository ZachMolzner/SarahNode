from __future__ import annotations

import pytest

from app.agent.contracts import PermissionScope
from app.agent.desktop_action_router import parse_desktop_action
from app.agent.desktop_action_tools import _BLOCKED_OPEN_SUFFIXES
from app.agent.permissions import default_policy
from app.agent.web_launch_tools import normalize_http_url


def test_open_supported_app_routes_to_app_launcher() -> None:
    request = parse_desktop_action("Open Opera")
    assert request is not None
    assert request.tool_name == "open_app"
    assert request.arguments == {"app": "Opera"}


def test_open_known_folder_routes_to_safe_path_opener() -> None:
    request = parse_desktop_action("Open my Downloads folder")
    assert request is not None
    assert request.tool_name == "open_path"
    assert request.arguments == {"path": "downloads"}


def test_open_url_routes_to_http_launcher() -> None:
    request = parse_desktop_action("Open example.com")
    assert request is not None
    assert request.tool_name == "open_url"
    assert request.arguments == {"url": "example.com"}


def test_focus_routes_without_launching() -> None:
    request = parse_desktop_action("Bring VS Code to the front")
    assert request is not None
    assert request.tool_name == "focus_app"
    assert request.arguments == {"app": "VS Code"}


def test_unique_filename_routes_to_path_opener() -> None:
    request = parse_desktop_action("Open budget.xlsx")
    assert request is not None
    assert request.tool_name == "open_path"
    assert request.arguments == {"path": "budget.xlsx"}


def test_destructive_command_is_not_auto_routed() -> None:
    assert parse_desktop_action("Delete my Downloads folder") is None
    assert parse_desktop_action("Kill Chrome") is None
    assert parse_desktop_action("Install Discord") is None


def test_ambiguous_open_phrase_is_not_auto_routed() -> None:
    assert parse_desktop_action("Open the thing we discussed") is None


def test_safe_url_normalization_only_allows_http_https() -> None:
    assert normalize_http_url("example.com") == "https://example.com"
    assert normalize_http_url("https://example.com/a") == "https://example.com/a"
    with pytest.raises(ValueError):
        normalize_http_url("file:///C:/Windows/System32")
    with pytest.raises(ValueError):
        normalize_http_url("javascript:alert(1)")


def test_active_content_extensions_are_blocked() -> None:
    for suffix in (".exe", ".bat", ".cmd", ".ps1", ".lnk", ".msi", ".docm", ".xlsm"):
        assert suffix in _BLOCKED_OPEN_SUFFIXES


def test_default_policy_grants_only_narrow_phase4b_side_effects() -> None:
    policy = default_policy()

    assert PermissionScope.APPS_LAUNCH in policy.granted_scopes
    assert PermissionScope.APPS_FOCUS in policy.granted_scopes
    assert PermissionScope.FILES_OPEN in policy.granted_scopes
    assert PermissionScope.WEB_LAUNCH in policy.granted_scopes

    assert PermissionScope.FILES_WRITE not in policy.granted_scopes
    assert PermissionScope.DESKTOP_CONTROL not in policy.granted_scopes
    assert PermissionScope.SYSTEM_CONTROL not in policy.granted_scopes
