from __future__ import annotations

from app.agent.automation import AutomationRegistry
from app.agent.builtin_tools import builtin_tools
from app.agent.desktop_action_tools import desktop_action_tools
from app.agent.desktop_tools import desktop_read_tools
from app.agent.event_bus import EventBus
from app.agent.permissions import default_policy
from app.agent.tool_registry import ToolRegistry


class SarahAgentRuntime:
    def __init__(self) -> None:
        self.permissions = default_policy()
        self.tools = ToolRegistry(self.permissions)
        self.tools.register_many(builtin_tools())
        self.tools.register_many(desktop_read_tools())
        self.tools.register_many(desktop_action_tools())
        self.events = EventBus()
        self.automations = AutomationRegistry()

    def capabilities(self) -> dict[str, object]:
        return {
            "architecture_version": 5,
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
                "app_focus": "allowlisted_active",
                "file_open": "safe_types_active",
                "url_launch": "http_https_active",
                "desktop_control": "strong_actions_still_gated",
                "screen_awareness": "planned",
                "web_tools": "provider_dependent",
                "personal_services": "planned",
                "voice": "planned",
                "smart_home": "planned",
            },
        }


agent_runtime = SarahAgentRuntime()
