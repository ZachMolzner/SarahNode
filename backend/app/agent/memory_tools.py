from __future__ import annotations

from typing import Any, Mapping

from app.agent.contracts import PermissionScope, RiskLevel, ToolDefinition
from app.memory.learning import MemoryLearningService
from app.schemas.identity import MemoryCategory


def memory_tools(memory: MemoryLearningService) -> list[ToolDefinition]:
    async def search_memory(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        query = str(arguments.get("query", "")).strip()
        scope = str(arguments.get("scope", "")).strip() or None
        category_raw = str(arguments.get("category", "")).strip()
        category = MemoryCategory(category_raw) if category_raw else None
        items = memory.search(query, scope=scope, category=category, limit=int(arguments.get("limit", 8)))
        return {
            "items": [item.model_dump(mode="json") for item in items],
            "count": len(items),
        }

    async def remember(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        item = memory.remember(
            scope=str(arguments.get("scope", "zach")),
            category=MemoryCategory(str(arguments.get("category", "knowledge"))),
            key=str(arguments.get("key", "memory")),
            value=str(arguments.get("value", "")),
            sensitive=bool(arguments.get("sensitive", False)),
        )
        return {"item": item.model_dump(mode="json")}

    async def update_memory(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        item_id = str(arguments.get("item_id", "")).strip()
        value = str(arguments.get("value", "")).strip()
        if not item_id or not value:
            raise ValueError("item_id and value are required")
        item = memory.identity_service.update_memory_item(item_id, {"value": value})
        return {"item": item.model_dump(mode="json")}

    async def forget_memory(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        item_id = str(arguments.get("item_id", "")).strip()
        if not item_id:
            raise ValueError("item_id is required")
        memory.forget(item_id=item_id)
        return {"forgotten": item_id}

    category_enum = [category.value for category in MemoryCategory if category is not MemoryCategory.identity]

    return [
        ToolDefinition(
            name="memory_search",
            description=(
                "Search Sarah's persistent memory. Use this when the user asks what Sarah remembers, "
                "or when retrieving a stored preference, project, goal, routine, experience, device, place, or fact would help."
            ),
            handler=search_memory,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "scope": {"type": "string"},
                    "category": {"type": "string", "enum": [category.value for category in MemoryCategory]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 25},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.MEMORY_READ}),
            risk=RiskLevel.READ_ONLY,
        ),
        ToolDefinition(
            name="memory_remember",
            description=(
                "Store or replace an explicit persistent memory only when the user clearly asks Sarah to remember/save/learn it. "
                "Do not silently store guesses or inferred sensitive information."
            ),
            handler=remember,
            parameters={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "description": "Usually zach, household, or a project name."},
                    "category": {"type": "string", "enum": category_enum},
                    "key": {"type": "string", "description": "Short stable identifier for this memory."},
                    "value": {"type": "string", "description": "The fact or preference to remember."},
                    "sensitive": {"type": "boolean"},
                },
                "required": ["scope", "category", "key", "value", "sensitive"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.MEMORY_WRITE}),
            risk=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="memory_update",
            description="Correct an existing persistent memory when the user explicitly says a remembered item is wrong or changed.",
            handler=update_memory,
            parameters={
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["item_id", "value"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.MEMORY_WRITE}),
            risk=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="memory_forget",
            description="Delete a specific persistent memory when the user explicitly asks Sarah to forget it.",
            handler=forget_memory,
            parameters={
                "type": "object",
                "properties": {"item_id": {"type": "string"}},
                "required": ["item_id"],
                "additionalProperties": False,
            },
            scopes=frozenset({PermissionScope.MEMORY_WRITE}),
            risk=RiskLevel.LOW,
        ),
    ]
