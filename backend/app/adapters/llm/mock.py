from typing import Any

from app.adapters.llm.base import LLMClient
from app.schemas.chat import AssistantReply, ChatMessage


class MockLLMClient(LLMClient):
    async def generate_reply(
        self,
        message: ChatMessage,
        memory_summary: str,
        persona: dict[str, Any],
    ) -> AssistantReply:
        return AssistantReply(
            text=(
                f"Mock mode active. I received: '{message.content}'. "
                f"Memory: {memory_summary[:120]}"
            ),
            emotion="neutral",
            should_speak=True,
        )
