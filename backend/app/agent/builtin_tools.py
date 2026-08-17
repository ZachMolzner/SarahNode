from __future__ import annotations

import os
import platform
from datetime import datetime
from typing import Any, Mapping

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition


async def current_time_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    now = datetime.now().astimezone()
    return {
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": str(now.tzinfo),
    }


async def system_info_handler(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }


def builtin_tools() -> list[ToolDefinition]:
    empty_parameters = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    return [
        ToolDefinition(
            name="current_time",
            description="Get the current local date, time, and timezone on the SarahNode host computer.",
            handler=current_time_handler,
            parameters=empty_parameters,
            scopes=frozenset({PermissionScope.SYSTEM_READ}),
            risk=RiskLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="system_info",
            description="Read basic non-sensitive information about the SarahNode host computer and Python runtime.",
            handler=system_info_handler,
            parameters=empty_parameters,
            scopes=frozenset({PermissionScope.SYSTEM_READ}),
            risk=RiskLevel.READ_ONLY,
        ),
    ]
