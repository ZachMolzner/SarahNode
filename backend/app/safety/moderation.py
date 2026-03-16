import re

from app.schemas.chat import ChatMessage, ModerationResult


class ModerationService:
    blocked_patterns: dict[str, re.Pattern[str]] = {
        "hate_abuse": re.compile(r"\b(slur|hate)\b", re.IGNORECASE),
        "sexual": re.compile(r"\b(explicit|nsfw)\b", re.IGNORECASE),
        "self_harm": re.compile(r"\b(self-harm|suicide)\b", re.IGNORECASE),
        "illegal": re.compile(r"\b(bomb|exploit|hack account)\b", re.IGNORECASE),
        "doxxing": re.compile(r"\b(address|phone number|ssn)\b", re.IGNORECASE),
        "prompt_injection": re.compile(r"ignore previous instructions|system prompt", re.IGNORECASE),
    }

    def evaluate(self, message: ChatMessage) -> ModerationResult:
        content = message.content.strip()
        for category, pattern in self.blocked_patterns.items():
            if pattern.search(content):
                return ModerationResult(
                    allowed=False,
                    reason="Blocked by moderation policy",
                    category=category,
                )
        return ModerationResult(allowed=True, reason="Allowed")
