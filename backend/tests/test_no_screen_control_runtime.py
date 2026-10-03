from app.agent.contracts import PermissionScope
from app.agent.runtime import agent_runtime


def test_runtime_has_no_screen_or_desktop_control_capabilities() -> None:
    tool_names = {tool.name for tool in agent_runtime.tools.list_tools(include_internal=True)}

    forbidden_tools = {
        "screen_metadata",
        "move_pointer",
        "click_pointer",
        "type_text",
        "replace_text_value",
        "scroll_pointer",
        "press_safe_key",
        "press_enter",
        "open_app",
        "focus_app",
        "open_path",
        "open_url",
        "create_folder",
        "create_file",
        "move_path",
        "recycle_path",
        "close_app",
        "terminate_app",
    }
    assert tool_names.isdisjoint(forbidden_tools)

    forbidden_scopes = {
        PermissionScope.SCREEN_READ,
        PermissionScope.SCREEN_POINTER,
        PermissionScope.SCREEN_CLICK,
        PermissionScope.SCREEN_TYPE,
        PermissionScope.SCREEN_SCROLL,
        PermissionScope.SCREEN_KEYS,
        PermissionScope.DESKTOP_CONTROL,
        PermissionScope.APPS_LAUNCH,
        PermissionScope.APPS_FOCUS,
        PermissionScope.APPS_CLOSE,
        PermissionScope.APPS_TERMINATE,
        PermissionScope.FILES_OPEN,
        PermissionScope.FILES_CREATE,
        PermissionScope.FILES_MOVE,
        PermissionScope.FILES_RECYCLE,
        PermissionScope.FILES_WRITE,
        PermissionScope.WEB_LAUNCH,
    }
    assert agent_runtime.permissions.granted_scopes.isdisjoint(forbidden_scopes)


def test_runtime_keeps_read_only_it_diagnostics() -> None:
    tool_names = {tool.name for tool in agent_runtime.tools.list_tools(include_internal=True)}
    assert {"system_resources", "running_processes"}.issubset(tool_names)
    assert PermissionScope.SYSTEM_READ in agent_runtime.permissions.granted_scopes
    assert PermissionScope.DESKTOP_READ in agent_runtime.permissions.granted_scopes
