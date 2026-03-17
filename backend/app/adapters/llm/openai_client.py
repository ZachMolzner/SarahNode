import logging
from typing import Any

from openai import AsyncOpenAI

from app.adapters.llm.base import LLMClient
from app.config.settings import settings
from app.schemas.chat import AssistantReply, ChatMessage

logger = logging.getLogger(__name__)


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        resolved_api_key = api_key or settings.openai_api_key
        if not resolved_api_key:
            raise ValueError("OPENAI_API_KEY must be set.")

        self.client = AsyncOpenAI(api_key=resolved_api_key)
        self.model = model or settings.openai_model

    async def generate_reply(
        self,
        message: ChatMessage,
        memory_summary: str,
        persona: dict[str, Any],
    ) -> AssistantReply:
        system_prompt = str(persona.get("system_prompt", settings.persona_system_prompt))
        persona_name = str(persona.get("name", settings.persona_name))
        persona_style = str(persona.get("style", settings.persona_style))

        response = await self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"{system_prompt} Persona name: {persona_name}. "
                                f"Conversation style: {persona_style}."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Memory summary: {memory_summary}\n"
                                f"User ({message.username}) says: {message.content}\n"
                                "Respond as the assistant in under 120 words."
                            ),
                        }
                    ],
                },
            ],
        )

        text = (response.output_text or "").strip()
        if not text:
            logger.warning("OpenAI returned empty text output")
            text = "I am here and ready. Could you try asking that another way?"

        lowered = text.lower()
        emotion = "calm"
        if any(keyword in lowered for keyword in ("great", "glad", "nice", "awesome")):
            emotion = "happy"
        elif any(keyword in lowered for keyword in ("sorry", "concern", "careful")):
            emotion = "concerned"

        return AssistantReply(text=text, emotion=emotion, should_speak=True)
