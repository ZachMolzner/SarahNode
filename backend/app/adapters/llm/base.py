from abc import ABC, abstractmethod
from typing import Any

from app.services.capability_router import CapabilityRoute

from app.schemas.chat import AssistantReply, ChatMessage


class LLMClient(ABC):
    @abstractmethod
    async def generate_reply(
        self,
        message: ChatMessage,
        memory_summary: str,
        recent_history: list[str],
        persona: dict[str, Any],
        capability_route: CapabilityRoute,
    ) -> AssistantReply:
        raise NotImplementedError
