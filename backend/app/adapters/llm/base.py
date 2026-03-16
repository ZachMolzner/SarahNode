from abc import ABC, abstractmethod

from app.schemas.chat import AssistantReply, ChatMessage


class LLMClient(ABC):
    @abstractmethod
    async def generate_reply(self, message: ChatMessage, memory_summary: str, persona: dict) -> AssistantReply:
        raise NotImplementedError
