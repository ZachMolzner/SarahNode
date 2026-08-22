from __future__ import annotations

import re
from dataclasses import dataclass

from app.memory.learning import MemoryLearningService
from app.memory.secret_guard import detect_persistent_secret
from app.schemas.identity import MemoryItem


_EXPLICIT_REMEMBER_INTENT_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:remember|save|learn)\s+(?:that\s+)?(.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ExplicitMemoryDecision:
    status: str
    item: MemoryItem | None = None


class SafeMemoryLearningService(MemoryLearningService):
    """Memory learner that refuses deterministic capture of credential-like text.

    Direct tool/API writes are still protected by SafeIdentityService. These overrides
    prevent an explicit chat command such as "remember my password is ..." from raising
    during context assembly or entering the normal memory-learning path at all.
    """

    def classify_explicit_memory_request(self, text: str) -> ExplicitMemoryDecision | None:
        if not _EXPLICIT_REMEMBER_INTENT_RE.match(text.strip()):
            return None
        if detect_persistent_secret(value=text) is not None:
            return ExplicitMemoryDecision(status="blocked_secret")

        parsed = self._parse_explicit_memory(text)
        if parsed is None:
            return ExplicitMemoryDecision(status="unsupported")
        return ExplicitMemoryDecision(status="safe_memory")

    def capture_explicit_memory(self, text: str, *, scope: str) -> MemoryItem | None:
        if detect_persistent_secret(value=text) is not None:
            return None
        return super().capture_explicit_memory(text, scope=scope)

    def capture_explicit_update(self, text: str, *, scope: str) -> MemoryItem | None:
        if detect_persistent_secret(value=text) is not None:
            return None
        return super().capture_explicit_update(text, scope=scope)
