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
        name = str(persona.get("name", "Nova"))
        tone = str(persona.get("tone", "helpful"))

        emotion = "emotion_happy" if "!" in message.content else "emotion_calm"

        text = (
            f"{name} here. Thanks, {message.username}! "
            f"You said: '{message.content[:120]}'. "
            f"My tone is {tone}. "
            f"Recent context: {memory_summary}."
        )

        return AssistantReply(
            text=text,
            emotion=emotion,
            should_speak=True,
        )
