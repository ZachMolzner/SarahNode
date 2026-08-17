from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.schemas.identity import MemoryCategory, MemoryItem, MemorySource
from app.services.identity_service import IdentityService


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_'-]+")


@dataclass(slots=True)
class MemoryLearningService:
    identity_service: IdentityService

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token.lower() for token in _TOKEN_RE.findall(text) if len(token) > 2}

    def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        category: MemoryCategory | None = None,
        limit: int = 8,
    ) -> list[MemoryItem]:
        query_tokens = self._tokens(query)
        items = self.identity_service.list_memory_items(scope=scope)
        if category is not None:
            items = [item for item in items if item.category == category]

        def score(item: MemoryItem) -> tuple[float, float]:
            searchable = f"{item.scope} {item.category.value} {item.key} {item.value}"
            item_tokens = self._tokens(searchable)
            overlap = len(query_tokens & item_tokens)
            phrase_bonus = 2 if query.strip().lower() in searchable.lower() else 0
            return (float(overlap + phrase_bonus), item.updated_at.timestamp())

        ranked = sorted(items, key=score, reverse=True)
        if query_tokens:
            ranked = [item for item in ranked if score(item)[0] > 0]
        return ranked[: max(1, min(limit, 25))]

    def remember(
        self,
        *,
        scope: str,
        category: MemoryCategory,
        key: str,
        value: str,
        sensitive: bool = False,
    ) -> MemoryItem:
        normalized_key = key.strip().lower().replace(" ", "_")
        for existing in self.identity_service.list_memory_items(scope=scope):
            if existing.key == normalized_key and existing.category == category:
                return self.identity_service.update_memory_item(
                    existing.id,
                    {
                        "value": value.strip(),
                        "confidence": 1.0,
                        "sensitive": sensitive,
                        "source": MemorySource.explicit,
                    },
                )

        return self.identity_service.add_memory_item(
            scope=scope.strip().lower(),
            category=category,
            source=MemorySource.explicit,
            key=normalized_key,
            value=value.strip(),
            confidence=1.0,
            sensitive=sensitive,
        )

    def forget(self, *, item_id: str) -> None:
        self.identity_service.delete_memory_item(item_id)

    def context_for(self, query: str, *, scopes: Iterable[str], limit: int = 8) -> str:
        candidates: dict[str, MemoryItem] = {}
        for scope in scopes:
            for item in self.search(query, scope=scope, limit=limit):
                if not item.sensitive:
                    candidates[item.id] = item

        # If semantic overlap is weak, still include a few recent explicit preferences/projects.
        if not candidates:
            fallback = [
                item
                for item in self.identity_service.list_memory_items()
                if not item.sensitive
                and item.scope in set(scopes)
                and item.category
                in {
                    MemoryCategory.preference,
                    MemoryCategory.project,
                    MemoryCategory.goal,
                    MemoryCategory.routine,
                }
            ]
            fallback.sort(key=lambda item: item.updated_at, reverse=True)
            candidates = {item.id: item for item in fallback[:limit]}

        if not candidates:
            return "No relevant persistent memories."

        ordered = sorted(candidates.values(), key=lambda item: item.updated_at, reverse=True)[:limit]
        return "\n".join(
            f"- [{item.category.value}/{item.scope}] {item.key}: {item.value}"
            for item in ordered
        )
