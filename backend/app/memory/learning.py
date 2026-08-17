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
_EXPLICIT_FORGET_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?forget\s+(?:that\s+)?(.+?)\s*$",
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

    @staticmethod
    def _favorite_parts(text: str) -> tuple[str, str] | None:
        match = re.search(
            r"\bmy\s+favorite\s+([a-zA-Z0-9 _-]+?)\s+is\s+(?:actually\s+)?(.+?)(?:\s+now)?(?:[.!?]|$)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        subject = match.group(1).strip()
        value = match.group(2).strip().rstrip(".")
        if not subject or not value:
            return None
        return subject, value

    def _logical_key(self, item: MemoryItem) -> str:
        key = item.key.strip().lower().replace(" ", "_")
        if key.startswith("favorite_"):
            return key

        favorite = self._favorite_parts(item.value)
        if favorite:
            subject, _value = favorite
            return f"favorite_{self._slug(subject, max_words=4)}"
        return key

    def _parse_explicit_memory(self, text: str) -> tuple[MemoryCategory, str, str] | None:
        match = _EXPLICIT_REMEMBER_RE.match(text.strip())
        if not match:
            return None

        value = match.group(1).strip().rstrip(".")
        if not value:
            return None

        lowered = value.lower()
        if lowered.startswith(("what ", "when ", "where ", "which ", "who ", "why ", "how ", "whether ")):
            return None

        favorite = self._favorite_parts(value)
        if favorite:
            subject, favorite_value = favorite
            return (
                MemoryCategory.preference,
                f"favorite_{self._slug(subject, max_words=4)}",
                f"My favorite {subject} is {favorite_value}",
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

    def capture_explicit_update(self, text: str, *, scope: str) -> MemoryItem | None:
        lowered = text.lower()
        favorite = self._favorite_parts(text)
        if not favorite:
            return None
        if not any(marker in lowered for marker in ("actually", "changed", "change", "update", "now")):
            return None

        subject, favorite_value = favorite
        key = f"favorite_{self._slug(subject, max_words=4)}"
        return self.remember(
            scope=scope,
            category=MemoryCategory.preference,
            key=key,
            value=f"My favorite {subject} is {favorite_value}",
            sensitive=False,
        )

    def capture_explicit_forget(self, text: str, *, scopes: Iterable[str]) -> list[str]:
        match = _EXPLICIT_FORGET_RE.match(text.strip())
        if not match:
            return []

        target = match.group(1).strip().rstrip(".")
        if not target:
            return []

        favorite_match = re.search(r"\b(?:my\s+)?favorite\s+(.+)$", target, re.IGNORECASE)
        logical_target: str | None = None
        if favorite_match:
            subject = favorite_match.group(1).strip()
            logical_target = f"favorite_{self._slug(subject, max_words=4)}"

        scope_set = {scope.strip().lower() for scope in scopes}
        target_tokens = self._tokens(target)
        removed: list[str] = []
        for item in list(self.identity_service.list_memory_items()):
            if item.scope not in scope_set:
                continue

            logical_key = self._logical_key(item)
            is_match = bool(logical_target and logical_key == logical_target)
            if not is_match and target_tokens:
                searchable_tokens = self._tokens(f"{item.key} {item.value}")
                is_match = target_tokens.issubset(searchable_tokens)

            if is_match:
                self.identity_service.delete_memory_item(item.id)
                removed.append(item.id)
        return removed

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

        # Treat a logical memory key as unique for a scope. Update the newest copy
        # and delete any stale duplicates left by older model-driven writes.
        matches = [
            item
            for item in self.identity_service.list_memory_items(scope=normalized_scope)
            if self._logical_key(item) == normalized_key
        ]
        if matches:
            matches.sort(key=lambda item: item.updated_at, reverse=True)
            primary = matches[0]
            updated = self.identity_service.update_memory_item(
                primary.id,
                {
                    "category": category,
                    "key": normalized_key,
                    "value": value.strip(),
                    "confidence": 1.0,
                    "sensitive": sensitive,
                    "source": MemorySource.explicit,
                },
            )
            for duplicate in matches[1:]:
                self.identity_service.delete_memory_item(duplicate.id)
            return updated

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
        scope_set = {scope.strip().lower() for scope in scopes}
        user_scopes = sorted(scope for scope in scope_set if scope != "household")
        write_scope = user_scopes[0] if user_scopes else "household"

        # Deterministic memory mutations happen before retrieval so the model sees
        # the new source of truth on the same turn.
        self.capture_explicit_forget(query, scopes=scope_set)
        self.capture_explicit_update(query, scope=write_scope)
        self.capture_explicit_memory(query, scope=write_scope)

        candidates: dict[str, MemoryItem] = {}
        for scope in scope_set:
            for item in self.search(query, scope=scope, limit=limit):
                if not item.sensitive:
                    candidates[item.id] = item

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

        # Never present conflicting stale copies of the same logical memory to the
        # model. The newest entry wins, with personal scope preferred over household.
        logical: dict[str, MemoryItem] = {}
        ordered_candidates = sorted(candidates.values(), key=lambda item: item.updated_at, reverse=True)
        for item in ordered_candidates:
            logical_key = self._logical_key(item)
            existing = logical.get(logical_key)
            if existing is None:
                logical[logical_key] = item
                continue
            if existing.scope == "household" and item.scope != "household":
                logical[logical_key] = item

        ordered = sorted(logical.values(), key=lambda item: item.updated_at, reverse=True)[:limit]
        return "\n".join(
            (
                f"- PERSISTENT [{item.category.value}/{item.scope}] "
                f"id={item.id} key={item.key}: {item.value}"
            )
            for item in ordered
        )
