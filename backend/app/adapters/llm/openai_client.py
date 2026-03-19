import logging
from typing import Any

from openai import AsyncOpenAI

from app.adapters.llm.base import LLMClient
from app.config.settings import settings
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.capability_router import CapabilityRoute

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
        recent_history: list[str],
        persona: dict[str, Any],
        capability_route: CapabilityRoute,
        system_prompt_override: str | None = None,
        user_prompt_override: str | None = None,
    ) -> AssistantReply:
        system_prompt = system_prompt_override or str(persona.get("system_prompt", settings.persona_system_prompt))
        persona_name = str(persona.get("name", settings.persona_name))
        persona_style = str(persona.get("style", settings.persona_style))

        history_text = "\n".join(recent_history[-8:]) if recent_history else "No prior turns recorded."

        response = await self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"{system_prompt}\n"
                                "You are a practical local-first personal assistant. "
                                "Give useful, concrete next steps. Keep responses concise by default unless asked for depth.\n"
                                f"Assistant persona name: {persona_name}\n"
                                f"Conversation style: {persona_style}\n"
                                f"Capability route: {capability_route.intent} (confidence={capability_route.confidence:.2f})\n"
                                f"Response style hint: {capability_route.style_hint}\n"
                                "If the user asks for live lookup/search and tools are not available, say that clearly and offer a concrete fallback plan."
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
                                user_prompt_override
                                or (
                                    f"Recent memory summary:\n{memory_summary}\n\n"
                                    f"Recent turns:\n{history_text}\n\n"
                                    f"New message from {message.username}: {message.content}"
                                )
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
