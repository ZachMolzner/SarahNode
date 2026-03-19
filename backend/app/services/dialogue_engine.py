import json
import logging
from pathlib import Path
from typing import Any

from app.adapters.llm.base import LLMClient
from app.adapters.llm.mock import MockLLMClient
from app.config.settings import settings
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.capability_router import CapabilityRoute, CapabilityRouter
from app.services.page_fetcher import PageFetcher
from app.services.web_answer_synthesizer import WebAnswerContext, WebAnswerSynthesizer
from app.services.web_browsing_policy import WebBrowsingPolicy
from app.services.web_search_service import WebSearchService

logger = logging.getLogger(__name__)


class DialogueEngine:
    def __init__(
        self,
        llm_client: LLMClient,
        persona_path: str = "app/config/persona.json",
        web_search_service: WebSearchService | None = None,
        page_fetcher: PageFetcher | None = None,
        web_browsing_policy: WebBrowsingPolicy | None = None,
        web_answer_synthesizer: WebAnswerSynthesizer | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.persona_path = Path(persona_path)
        self.persona = self._load_persona()
        self.capability_router = CapabilityRouter()
        self.web_search_service = web_search_service
        self.page_fetcher = page_fetcher
        self.web_browsing_policy = web_browsing_policy or WebBrowsingPolicy()
        self.web_answer_synthesizer = web_answer_synthesizer or WebAnswerSynthesizer()
        self.last_web_context: WebAnswerContext | None = None

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
        self.last_web_context = None
        decision = self.web_browsing_policy.decide(message.content, capability_route)

        if decision.should_browse:
            if not self.web_search_service or not self.web_search_service.status.enabled:
                return self.web_answer_synthesizer.unavailable_reply()

            search_results = await self.web_search_service.search(message.content)
            fetched_pages = []
            if self.page_fetcher:
                fetched_pages = await self.page_fetcher.fetch_pages(search_results)

            self.last_web_context = WebAnswerContext(
                checked_web=True,
                provider=self.web_search_service.status.provider,
                search_results=search_results,
                fetched_pages=fetched_pages,
                decision_reason=decision.reason,
            )

            if not search_results:
                return AssistantReply(
                    text=(
                        "I checked the web, but I couldn’t find strong results for that query. "
                        "If you want, I can try a narrower search phrase or focus on a specific source."
                    ),
                    emotion="concerned",
                    should_speak=True,
                )

            web_user_prompt = self.web_answer_synthesizer.build_web_prompt(message, self.last_web_context)
            return await self._generate_with_fallback(
                message,
                memory_summary,
                recent_history,
                capability_route,
                system_prompt_override=(
                    "You are Sarah. You perform web-grounded answers when web evidence is provided. "
                    "Be explicit that you checked the web, stay concise, and be honest about uncertainty."
                ),
                user_prompt_override=web_user_prompt,
            )

        return await self._generate_with_fallback(
            message,
            memory_summary,
            recent_history,
            capability_route,
        )

    async def _generate_with_fallback(
        self,
        message: ChatMessage,
        memory_summary: str,
        recent_history: list[str],
        capability_route: CapabilityRoute,
        system_prompt_override: str | None = None,
        user_prompt_override: str | None = None,
    ) -> AssistantReply:
        try:
            return await self.llm_client.generate_reply(
                message=message,
                memory_summary=memory_summary,
                recent_history=recent_history,
                persona=self.persona,
                capability_route=capability_route,
                system_prompt_override=system_prompt_override,
                user_prompt_override=user_prompt_override,
            )
        except Exception:
            logger.exception("Primary LLM client failed, using mock fallback")
            return await MockLLMClient().generate_reply(
                message=message,
                memory_summary=memory_summary,
                recent_history=recent_history,
                persona=self.persona,
                capability_route=capability_route,
                system_prompt_override=system_prompt_override,
                user_prompt_override=user_prompt_override,
            )
