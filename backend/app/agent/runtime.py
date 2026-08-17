from __future__ import annotations

from app.agent.automation import AutomationRegistry
from app.agent.builtin_tools import builtin_tools
from app.agent.event_bus import EventBus
from app.agent.permissions import default_policy
from app.agent.tool_registry import ToolRegistry


class SarahAgentRuntime:
    def __init__(self) -> None:
        self.permissions = default_policy()
        self.tools = ToolRegistry(self.permissions)
        self.tools.register_many(builtin_tools())
        self.events = EventBus()
        self.automations = AutomationRegistry()

    def capabilities(self) -> dict[str, object]:
        return {
            "architecture_version": 3,
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
                "desktop_tools": "planned",
                "web_tools": "provider_dependent",
                "personal_services": "planned",
                "voice": "planned",
                "screen_awareness": "planned",
                "smart_home": "planned",
            },
        }


agent_runtime = SarahAgentRuntime()
