from typing import Any

from app.adapters.llm.base import LLMClient
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.capability_router import CapabilityRoute


class MockLLMClient(LLMClient):
    async def generate_reply(
        self,
        message: ChatMessage,
        memory_summary: str,
        recent_history: list[str],
        persona: dict[str, Any],
        capability_route: CapabilityRoute,
        system_prompt_override: str | None = None,
        user_prompt_override: str | None = None,
    ) -> AssistantReply:
        return AssistantReply(
            text=(
                f"Mock mode active. I received: '{message.content}'. "
                f"Memory: {memory_summary[:120]}"
                f" | Turns: {len(recent_history)}"
                f" | Intent: {capability_route.intent}"
            ),
            emotion="neutral",
            should_speak=True,
        )
