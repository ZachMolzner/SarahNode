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
        text = f"{name}: I saw '{message.content[:120]}'. Context: {memory_summary}."
        emotion = "emotion_happy" if "!" in message.content else "emotion_confused"
        return AssistantReply(text=text, emotion=emotion, should_speak=True)
