from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PermissionScope(str, Enum):
    FILES_READ = "files.read"
    FILES_OPEN = "files.open"
    FILES_WRITE = "files.write"
    DESKTOP_READ = "desktop.read"
    DESKTOP_CONTROL = "desktop.control"
    APPS_LAUNCH = "apps.launch"
    APPS_FOCUS = "apps.focus"
    WEB_READ = "web.read"
    WEB_LAUNCH = "web.launch"
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    COMMUNICATIONS_READ = "communications.read"
    COMMUNICATIONS_SEND = "communications.send"
    CALENDAR_READ = "calendar.read"
    CALENDAR_WRITE = "calendar.write"
    AUTOMATION_MANAGE = "automation.manage"
    SMART_HOME_READ = "smart_home.read"
    SMART_HOME_CONTROL = "smart_home.control"
    SYSTEM_READ = "system.read"
    SYSTEM_CONTROL = "system.control"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    handler: Callable[[Mapping[str, Any]], Awaitable[Mapping[str, Any]]]
    parameters: Mapping[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
    )
    scopes: frozenset[PermissionScope] = field(default_factory=frozenset)
    risk: RiskLevel = RiskLevel.READ_ONLY
    requires_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    tool_name: str
    arguments: Mapping[str, Any]
    requested_by: str = "assistant"


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    tool_name: str
    data: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class SarahEvent:
    topic: str
    payload: Mapping[str, Any]
