from __future__ import annotations

from app.memory.learning import MemoryLearningService
from app.memory.secret_guard import detect_persistent_secret
from app.schemas.identity import MemoryItem


class SafeMemoryLearningService(MemoryLearningService):
    """Memory learner that refuses deterministic capture of credential-like text.

    Direct tool/API writes are still protected by SafeIdentityService. These overrides
    prevent an explicit chat command such as "remember my password is ..." from raising
    during context assembly or entering the normal memory-learning path at all.
    """

    def capture_explicit_memory(self, text: str, *, scope: str) -> MemoryItem | None:
        if detect_persistent_secret(value=text) is not None:
            return None
        return super().capture_explicit_memory(text, scope=scope)

    def capture_explicit_update(self, text: str, *, scope: str) -> MemoryItem | None:
        if detect_persistent_secret(value=text) is not None:
            return None
        return super().capture_explicit_update(text, scope=scope)
