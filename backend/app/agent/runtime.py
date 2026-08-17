from __future__ import annotations

from dataclasses import replace

from app.agent.automation import AutomationRegistry
from app.agent.builtin_tools import builtin_tools
from app.agent.confirmed_action_tools import confirmed_action_tools
from app.agent.desktop_action_tools import desktop_action_tools
from app.agent.desktop_tools import desktop_read_tools
from app.agent.event_bus import EventBus
from app.agent.permissions import default_policy
from app.agent.tool_registry import ToolRegistry
from app.agent.web_launch_tools import safe_open_url_tool
from app.agent.windows_focus_tools import hardened_focus_app_tool


class SarahAgentRuntime:
    def __init__(self) -> None:
        self.permissions = default_policy()
        self.tools = ToolRegistry(self.permissions)
        self.tools.register_many(builtin_tools())
        self.tools.register_many(desktop_read_tools())

        # Phase 4B low-risk actions can execute immediately when explicitly requested.
        action_tools = [
            replace(
                tool,
                description=(
                    "Use only when the user explicitly asks Sarah to perform this desktop action now. "
                    "Never use for hypothetical questions, instructions, or suggestions. "
                    + tool.description
                ),
            )
            for tool in desktop_action_tools()
            if tool.name not in {"open_url", "focus_app"}
        ]
        self.tools.register_many(action_tools)
        self.tools.register(hardened_focus_app_tool())
        self.tools.register(safe_open_url_tool())

        # Phase 4C mutation tools are MEDIUM risk and require confirmed=True at the
        # ToolRegistry boundary. The dialogue layer stages these actions first, so a
        # local model cannot execute them merely by producing a tool call.
        self.tools.register_many(confirmed_action_tools())

        self.events = EventBus()
        self.automations = AutomationRegistry()

    def capabilities(self) -> dict[str, object]:
        return {
            "architecture_version": 6,
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
                "model_gateway": "active",
                "tool_registry": "active",
                "permissions": "active",
                "event_bus": "ready",
                "automations": "scaffolded",
                "desktop_tools": "read_only_active",
                "file_search": "read_only_active",
                "safe_desktop_actions": "active",
                "app_launch": "allowlisted_active",
                "app_focus": "verified_foreground_active",
                "file_open": "safe_types_active",
                "url_launch": "http_https_active",
                "confirmed_file_create": "active",
                "confirmed_file_move_rename": "active",
                "confirmed_recycle_bin": "active",
                "confirmed_app_close": "active",
                "permanent_delete": "not_available",
                "force_process_kill": "not_available",
                "broad_desktop_control": "still_gated",
                "screen_awareness": "planned",
                "web_tools": "provider_dependent",
                "personal_services": "planned",
                "voice": "planned",
                "smart_home": "planned",
            },
        }


agent_runtime = SarahAgentRuntime()
