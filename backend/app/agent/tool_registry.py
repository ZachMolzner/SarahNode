from __future__ import annotations

from collections.abc import Iterable

from app.agent.contracts import ToolDefinition, ToolInvocation, ToolResult
from app.agent.permissions import PermissionDenied, PermissionPolicy


class ToolRegistry:
    def __init__(self, policy: PermissionPolicy) -> None:
        self._policy = policy
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def register_many(self, tools: Iterable[ToolDefinition]) -> None:
        for tool in tools:
            self.register(tool)

    def list_tools(self, *, include_internal: bool = False) -> list[ToolDefinition]:
        tools = self._tools.values()
        if not include_internal:
            tools = (tool for tool in tools if tool.model_visible)
        return sorted(tools, key=lambda tool: tool.name)

    async def invoke(self, invocation: ToolInvocation, *, confirmed: bool = False) -> ToolResult:
        tool = self._tools.get(invocation.tool_name)
        if tool is None:
            return ToolResult(ok=False, tool_name=invocation.tool_name, error="Unknown tool")

        try:
            self._policy.authorize(tool, confirmed=confirmed)
            data = await tool.handler(invocation.arguments)
            return ToolResult(ok=True, tool_name=tool.name, data=data)
        except PermissionDenied as exc:
            return ToolResult(ok=False, tool_name=tool.name, error=str(exc))
        except Exception as exc:
            return ToolResult(ok=False, tool_name=tool.name, error=f"Tool failed: {exc}")
