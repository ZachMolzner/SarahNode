from dataclasses import dataclass
from typing import Literal

CapabilityIntent = Literal[
    "ask_general",
    "lookup_information",
    "browse_web",
    "coding_help",
    "shutdown_command",
    "smalltalk_or_greeting",
]


@dataclass(frozen=True)
class CapabilityRoute:
    intent: CapabilityIntent
    confidence: float
    requires_web_lookup: bool
    style_hint: str


class CapabilityRouter:
    """Lightweight intent router for practical assistant capability steering."""

    def classify(self, content: str) -> CapabilityRoute:
        text = content.strip().lower()

        if self._is_shutdown(text):
            return CapabilityRoute(
                intent="shutdown_command",
                confidence=0.95,
                requires_web_lookup=False,
                style_hint="Confirm intent and prioritize safe graceful shutdown guidance.",
            )

        if self._is_browse_request(text):
            return CapabilityRoute(
                intent="browse_web",
                confidence=0.86,
                requires_web_lookup=True,
                style_hint=(
                    "Be explicit that live browsing/search may require tool/runtime support. "
                    "If unavailable, provide a clear best-effort plan and what to verify online."
                ),
            )

        if self._is_coding_help(text):
            return CapabilityRoute(
                intent="coding_help",
                confidence=0.84,
                requires_web_lookup=False,
                style_hint=(
                    "Respond in structured coding-assistant mode: diagnose issue, propose implementation steps, "
                    "and include concise examples when useful."
                ),
            )

        if self._is_lookup_request(text):
            return CapabilityRoute(
                intent="lookup_information",
                confidence=0.78,
                requires_web_lookup=True,
                style_hint=(
                    "Focus on factual lookup/explanation. Distinguish known context from data that should be verified via search."
                ),
            )

        if self._is_smalltalk(text):
            return CapabilityRoute(
                intent="smalltalk_or_greeting",
                confidence=0.8,
                requires_web_lookup=False,
                style_hint="Keep it warm and concise while staying helpful.",
            )

        return CapabilityRoute(
            intent="ask_general",
            confidence=0.65,
            requires_web_lookup=False,
            style_hint="Answer directly first, then add practical next steps.",
        )

    def _is_browse_request(self, text: str) -> bool:
        keywords = (
            "search the web",
            "browse",
            "look this up",
            "find information",
            "research",
            "compare these",
            "latest",
            "recent",
            "today",
        )
        return any(keyword in text for keyword in keywords)

    def _is_lookup_request(self, text: str) -> bool:
        keywords = (
            "what is",
            "who is",
            "explain",
            "tell me about",
            "information about",
            "why does",
            "how does",
            "difference between",
        )
        return any(keyword in text for keyword in keywords)

    def _is_coding_help(self, text: str) -> bool:
        keywords = (
            "code",
            "debug",
            "bug",
            "stack trace",
            "python",
            "javascript",
            "typescript",
            "rust",
            "sql",
            "function",
            "refactor",
            "test failure",
            "api",
        )
        return any(keyword in text for keyword in keywords)

    def _is_shutdown(self, text: str) -> bool:
        keywords = ("shutdown", "shut down", "close app", "close program", "exit")
        return any(keyword in text for keyword in keywords)

    def _is_smalltalk(self, text: str) -> bool:
        keywords = ("hi", "hello", "hey", "good morning", "good evening", "how are you")
        return any(text == keyword or text.startswith(f"{keyword} ") for keyword in keywords)
