from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.schemas.identity import MemoryCategory, MemoryItem, MemorySource
from app.services.identity_service import IdentityService


_TOKEN_RE = re.compile(r"[a-zA-Z0-9'-]+")
_EXPLICIT_REMEMBER_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:remember|save|learn)\s+(?:that\s+)?(.+?)\s*$",
    re.IGNORECASE,
)
_STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "how",
    "are",
    "was",
    "were",
    "have",
    "has",
    "had",
    "you",
    "your",
    "yours",
    "mine",
    "about",
}


@dataclass(slots=True)
class MemoryLearningService:
    identity_service: IdentityService

    @staticmethod
    def _tokens(text: str) -> set[str]:
        # Memory keys are intentionally snake_case (for example favorite_color).
        # Treat underscores and punctuation as word separators so natural-language
        # questions such as "what is my favorite color" match those keys.
        normalized = text.replace("_", " ").replace("-", " ")
        return {
            token.lower()
            for token in _TOKEN_RE.findall(normalized)
            if len(token) > 2 and token.lower() not in _STOPWORDS
        }

    @staticmethod
    def _slug(text: str, *, max_words: int = 6) -> str:
        words = [
            token.lower()
            for token in _TOKEN_RE.findall(text.replace("_", " ").replace("-", " "))
            if token.lower() not in _STOPWORDS
        ][:max_words]
        return "_".join(words) or "memory"

    def _parse_explicit_memory(self, text: str) -> tuple[MemoryCategory, str, str] | None:
        match = _EXPLICIT_REMEMBER_RE.match(text.strip())
        if not match:
            return None

        value = match.group(1).strip().rstrip(".")
        if not value:
            return None

        # Questions such as "remember what I said?" are retrieval requests, not writes.
        lowered = value.lower()
        if lowered.startswith(("what ", "when ", "where ", "which ", "who ", "why ", "how ", "whether ")):
            return None

        favorite_match = re.search(
            r"\bmy\s+favorite\s+([a-zA-Z0-9 _-]+?)\s+is\s+(.+)$",
            value,
            re.IGNORECASE,
        )
        if favorite_match:
            subject = favorite_match.group(1).strip()
            return (
                MemoryCategory.preference,
                f"favorite_{self._slug(subject, max_words=4)}",
                value,
            )

        if re.search(r"\b(?:i\s+prefer|my\s+preference|i\s+like)\b", lowered):
            return MemoryCategory.preference, f"preference_{self._slug(value)}", value
        if re.search(r"\b(?:goal|my\s+goal|i\s+want\s+to|i\s+plan\s+to)\b", lowered):
            return MemoryCategory.goal, f"goal_{self._slug(value)}", value
        if re.search(r"\b(?:project|sarahnode)\b", lowered):
            return MemoryCategory.project, f"project_{self._slug(value)}", value
        if re.search(r"\b(?:routine|every\s+day|every\s+morning|every\s+night)\b", lowered):
            return MemoryCategory.routine, f"routine_{self._slug(value)}", value
        if re.search(r"\b(?:habit|usually|normally)\b", lowered):
            return MemoryCategory.habit, f"habit_{self._slug(value)}", value
        if re.search(r"\b(?:wife|husband|spouse|friend|brother|sister|mother|father)\b", lowered):
            return MemoryCategory.relationship, f"relationship_{self._slug(value)}", value
        if re.search(r"\b(?:computer|pc|phone|tablet|laptop|device)\b", lowered):
            return MemoryCategory.device, f"device_{self._slug(value)}", value
        if re.search(r"\b(?:live\s+in|live\s+at|located\s+in|address|place)\b", lowered):
            return MemoryCategory.place, f"place_{self._slug(value)}", value

        return MemoryCategory.knowledge, self._slug(value), value

    def capture_explicit_memory(self, text: str, *, scope: str) -> MemoryItem | None:
        parsed = self._parse_explicit_memory(text)
        if not parsed:
            return None
        category, key, value = parsed
        return self.remember(
            scope=scope,
            category=category,
            key=key,
            value=value,
            sensitive=False,
        )

    def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        category: MemoryCategory | None = None,
        limit: int = 8,
    ) -> list[MemoryItem]:
        query_tokens = self._tokens(query)
        query_phrase = " ".join(sorted(query_tokens))
        items = self.identity_service.list_memory_items(scope=scope)
        if category is not None:
            items = [item for item in items if item.category == category]

        def score(item: MemoryItem) -> tuple[float, float]:
            key_words = item.key.replace("_", " ").replace("-", " ")
            searchable = f"{item.scope} {item.category.value} {key_words} {item.value}"
            item_tokens = self._tokens(searchable)
            overlap = len(query_tokens & item_tokens)

            # Prefer memories whose stable key closely matches the user's wording.
            key_tokens = self._tokens(key_words)
            key_overlap = len(query_tokens & key_tokens)
            key_coverage = key_overlap / max(1, len(key_tokens))
            query_coverage = overlap / max(1, len(query_tokens))

            phrase_bonus = 0.0
            lowered_query = query.strip().lower()
            lowered_searchable = searchable.lower()
            if lowered_query and lowered_query in lowered_searchable:
                phrase_bonus += 3.0
            if query_phrase and query_phrase in " ".join(sorted(item_tokens)):
                phrase_bonus += 1.0

            relevance = (
                float(overlap)
                + (key_overlap * 2.0)
                + (key_coverage * 2.0)
                + query_coverage
                + phrase_bonus
            )
            return (relevance, item.updated_at.timestamp())

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
        normalized_scope = scope.strip().lower()
        for existing in self.identity_service.list_memory_items(scope=normalized_scope):
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
            scope=normalized_scope,
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
        scope_set = set(scopes)

        # Explicit memory commands are persisted by the backend before the model
        # sees the turn. This guarantees that a small local model cannot merely
        # claim it remembered something without actually writing it to disk.
        user_scopes = sorted(scope for scope in scope_set if scope != "household")
        write_scope = user_scopes[0] if user_scopes else "household"
        self.capture_explicit_memory(query, scope=write_scope)

        candidates: dict[str, MemoryItem] = {}
        for scope in scope_set:
            for item in self.search(query, scope=scope, limit=limit):
                if not item.sensitive:
                    candidates[item.id] = item

        # If semantic overlap is weak, still include a few recent explicit
        # preferences/projects/goals so a small local model has useful continuity.
        if not candidates:
            fallback = [
                item
                for item in self.identity_service.list_memory_items()
                if not item.sensitive
                and item.scope in scope_set
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
            (
                f"- PERSISTENT [{item.category.value}/{item.scope}] "
                f"id={item.id} key={item.key}: {item.value}"
            )
            for item in ordered
        )
