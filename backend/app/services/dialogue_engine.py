import json
from pathlib import Path

from app.adapters.llm.base import LLMClient
from app.schemas.chat import AssistantReply, ChatMessage


class DialogueEngine:
    def __init__(self, llm_client: LLMClient, persona_path: str = "app/config/persona.json") -> None:
        self.llm_client = llm_client
        self.persona_path = Path(persona_path)
        self.persona = self._load_persona()

    def _load_persona(self) -> dict:
        with self.persona_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    async def generate(self, message: ChatMessage, memory_summary: str) -> AssistantReply:
        return await self.llm_client.generate_reply(message=message, memory_summary=memory_summary, persona=self.persona)
