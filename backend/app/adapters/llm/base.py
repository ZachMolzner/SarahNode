from abc import ABC, abstractmethod
from typing import Any

from app.schemas.chat import AssistantReply, ChatMessage
from app.services.capability_router import CapabilityRoute


class LLMClient(ABC):
    @abstractmethod
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
        raise NotImplementedError
