from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class AutomationDefinition:
    id: str
    name: str
    trigger_type: str
    trigger_config: Mapping[str, Any]
    action_tool: str
    action_arguments: Mapping[str, Any]
    enabled: bool = True
    created_at: datetime = datetime.now()


class AutomationRegistry:
    def __init__(self) -> None:
        self._items: dict[str, AutomationDefinition] = {}

    def upsert(self, automation: AutomationDefinition) -> None:
        self._items[automation.id] = automation

    def remove(self, automation_id: str) -> None:
        self._items.pop(automation_id, None)

    def list(self) -> list[AutomationDefinition]:
        return sorted(self._items.values(), key=lambda item: item.name.lower())

    def get(self, automation_id: str) -> AutomationDefinition | None:
        return self._items.get(automation_id)
