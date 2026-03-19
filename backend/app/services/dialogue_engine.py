import json
import logging
from pathlib import Path
from typing import Any

from app.adapters.llm.base import LLMClient
from app.adapters.llm.mock import MockLLMClient
from app.config.settings import settings
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.capability_router import CapabilityRoute, CapabilityRouter

logger = logging.getLogger(__name__)


class DialogueEngine:
    def __init__(self, llm_client: LLMClient, persona_path: str = "app/config/persona.json") -> None:
        self.llm_client = llm_client
        self.persona_path = Path(persona_path)
        self.persona = self._load_persona()
        self.capability_router = CapabilityRouter()

    def _load_persona(self) -> dict[str, Any]:
        if not self.persona_path.exists():
            return {
                "name": settings.persona_name,
                "style": settings.persona_style,
                "system_prompt": settings.persona_system_prompt,
            }

        with self.persona_path.open("r", encoding="utf-8") as file:
            parsed = json.load(file)

        return {
            "name": parsed.get("name", settings.persona_name),
            "style": parsed.get("style", settings.persona_style),
            "system_prompt": parsed.get("system_prompt", settings.persona_system_prompt),
        }

    def classify_capability(self, message: ChatMessage) -> CapabilityRoute:
        return self.capability_router.classify(message.content)

    async def generate(
        self,
        message: ChatMessage,
        memory_summary: str,
        recent_history: list[str],
        capability_route: CapabilityRoute,
    ) -> AssistantReply:
        try:
            return await self.llm_client.generate_reply(
                message=message,
                memory_summary=memory_summary,
                recent_history=recent_history,
                persona=self.persona,
                capability_route=capability_route,
            )
        except Exception:
            logger.exception("Primary LLM client failed, using mock fallback")
            return await MockLLMClient().generate_reply(
                message=message,
                memory_summary=memory_summary,
                recent_history=recent_history,
                persona=self.persona,
                capability_route=capability_route,
            )
