from __future__ import annotations

import re
from dataclasses import dataclass

from app.memory.learning import MemoryLearningService
from app.memory.secret_guard import detect_persistent_secret
from app.schemas.identity import MemoryCategory, MemoryItem, MemorySource


_EXPLICIT_REMEMBER_INTENT_RE = re.compile(
    r"^(?:sarah[,:]?\s+)?(?:please\s+)?(?:remember|save|learn)\s+(?:that\s+)?(.+?)\s*$",
    re.IGNORECASE,
)

_SUCCESS_FEEDBACK_RE = re.compile(
    r"\b(?:that worked|that fixed it|that solved it|that did it|it worked|it works now|"
    r"this worked|problem solved|fixed now|working now)\b",
    re.IGNORECASE,
)
_CORRECTION_FEEDBACK_RE = re.compile(
    r"\b(?:the actual fix|actual fix|what fixed it|the fix)\s+(?:was|is)\s+(.+?)(?:[.!?]|$)",
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

    @staticmethod
    def _compact_experience_text(text: str, limit: int = 700) -> str:
        cleaned = re.sub(r"```[\s\S]*?```", " [code omitted] ", str(text or ""))
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:limit].rstrip()

    def capture_outcome_feedback(
        self,
        feedback_text: str,
        *,
        previous_user_text: str,
        previous_reply: str,
        scope: str,
    ) -> MemoryItem | None:
        """Learn only from explicit user-confirmed troubleshooting outcomes.

        Sarah never treats her own answer as truth by itself. A durable experience is
        written only when the user confirms success or explicitly supplies the actual fix.
        """
        feedback = str(feedback_text or "").strip()
        problem = self._compact_experience_text(previous_user_text, limit=420)
        previous_solution = self._compact_experience_text(previous_reply, limit=700)
        if not feedback or not problem:
            return None

        correction = _CORRECTION_FEEDBACK_RE.search(feedback)
        success = _SUCCESS_FEEDBACK_RE.search(feedback)
        if correction is None and success is None:
            return None

        secret_probe = f"{feedback} {problem} {previous_solution}"
        if detect_persistent_secret(value=secret_probe) is not None:
            return None

        key = f"successful_fix_{self._slug(problem, max_words=8)}"
        if correction is not None:
            fix = self._compact_experience_text(correction.group(1), limit=500)
            value = f"Problem: {problem}. User-confirmed fix: {fix}"
        elif previous_solution:
            value = (
                f"Problem: {problem}. The user confirmed Sarah's previous troubleshooting "
                f"answer solved it. Successful answer: {previous_solution}"
            )
        else:
            return None

        normalized_scope = str(scope or "household").strip().lower()
        existing = [
            item
            for item in self.identity_service.list_memory_items(scope=normalized_scope)
            if item.key == key
        ]
        if existing:
            existing.sort(key=lambda item: item.updated_at, reverse=True)
            return self.identity_service.update_memory_item(
                existing[0].id,
                {
                    "category": MemoryCategory.experience,
                    "source": MemorySource.inferred,
                    "value": value,
                    "confidence": 0.9,
                    "sensitive": False,
                },
            )

        return self.identity_service.add_memory_item(
            scope=normalized_scope,
            category=MemoryCategory.experience,
            source=MemorySource.inferred,
            key=key,
            value=value,
            confidence=0.9,
            sensitive=False,
        )

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
