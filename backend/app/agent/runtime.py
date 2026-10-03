from __future__ import annotations

from app.agent.automation import AutomationRegistry
from app.agent.builtin_tools import builtin_tools
from app.agent.desktop_tools import desktop_read_tools
from app.agent.event_bus import EventBus
from app.agent.permissions import default_policy
from app.agent.tool_registry import ToolRegistry


class SarahAgentRuntime:
    """Knowledge-first Sarah runtime.

    SarahNode no longer exposes screen capture, pointer/keyboard injection, app launch,
    file mutation, or other desktop-control tools. A small read-only diagnostics surface
    remains available for IT troubleshooting: system information/resources and process
    inspection. Coding, research, and general questions continue through the model,
    memory, and web-research layers.
    """

    def __init__(self) -> None:
        self.permissions = default_policy()
        self.tools = ToolRegistry(self.permissions)
        self.tools.register_many(builtin_tools())

        # Keep only machine diagnostics that cannot manipulate the desktop or inspect
        # screen contents. active_window/find_files are intentionally omitted.
        diagnostics = [
            tool
            for tool in desktop_read_tools()
            if tool.name in {"system_resources", "running_processes"}
        ]
        self.tools.register_many(diagnostics)

        self.events = EventBus()
        self.automations = AutomationRegistry()

    def capabilities(self) -> dict[str, object]:
        return {
            "architecture_version": 15,
            "tool_count": len(self.tools.list_tools()),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "risk": tool.risk.value,
                    "scopes": sorted(scope.value for scope in tool.scopes),
                    "requires_confirmation": self.permissions.requires_confirmation(tool),
                }
                for tool in self.tools.list_tools()
            ],
            "granted_scopes": sorted(scope.value for scope in self.permissions.granted_scopes),
            "automation_count": len(self.automations.list()),
            "systems": {
                "memory": "persistent_learning_active",
                "memory_secret_guard": "credential_writes_and_session_recall_blocked",
                "model_gateway": "active",
                "tool_registry": "knowledge_first_read_only_diagnostics",
                "permissions": "screen_and_desktop_control_revoked",
                "event_bus": "ready",
                "automations": "scaffolded",
                "it_help": "active",
                "coding_help": "active",
                "general_qa": "active",
                "web_research": "provider_dependent",
                "system_info": "read_only_active",
                "system_resources": "read_only_active",
                "running_processes": "read_only_active",
                "screen_awareness": "removed",
                "screen_capture": "removed",
                "screen_pointer": "removed",
                "screen_keyboard": "removed",
                "screen_click": "removed",
                "ui_automation": "removed",
                "desktop_actions": "removed",
                "app_launch": "removed",
                "file_mutation": "removed",
                "browser_ui_automation": "removed",
                "avatar": "display_only_runtime",
                "personal_services": "planned",
                "voice": "optional",
                "smart_home": "not_planned",
            },
        }


agent_runtime = SarahAgentRuntime()
