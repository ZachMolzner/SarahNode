from __future__ import annotations

from typing import Any

from app.memory.secret_guard import detect_persistent_secret, ensure_memory_safe
from app.schemas.identity import MemoryCategory, MemoryItem, MemorySource
from app.services.identity_service import IdentityService


class SafeIdentityService(IdentityService):
    """Identity store with a hard credential/secret boundary for memory items.

    The base IdentityService still owns profiles and persistence mechanics. This subclass
    intercepts every memory add/update before disk I/O and also suppresses legacy secret-
    shaped rows from normal list/retrieval calls. Deletion still works by id.
    """

    def add_memory_item(
        self,
        scope: str,
        category: MemoryCategory,
        source: MemorySource,
        key: str,
        value: str,
        confidence: float,
        sensitive: bool,
    ) -> MemoryItem:
        ensure_memory_safe(key=key, value=value)
        return super().add_memory_item(
            scope=scope,
            category=category,
            source=source,
            key=key,
            value=value,
            confidence=confidence,
            sensitive=sensitive,
        )

    def update_memory_item(self, item_id: str, patch: dict[str, Any]) -> MemoryItem:
        existing: dict[str, Any] | None = None
        for raw in self._state.get("memory_items", []):
            if raw.get("id") == item_id:
                existing = raw
                break
        if existing is None:
            raise KeyError(item_id)

        next_key = str(patch.get("key", existing.get("key", "")))
        next_value = str(patch.get("value", existing.get("value", "")))
        ensure_memory_safe(key=next_key, value=next_value)
        return super().update_memory_item(item_id, patch)

    def list_memory_items(self, scope: str | None = None) -> list[MemoryItem]:
        items = super().list_memory_items(scope=scope)
        # Pre-hardening stores may contain a secret-shaped row that was not marked
        # sensitive. Keep it out of model/API retrieval without silently deleting data.
        return [
            item
            for item in items
            if detect_persistent_secret(key=item.key, value=item.value) is None
        ]
