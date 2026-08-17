import json
import logging
from pathlib import Path
from typing import Any

from app.adapters.llm.base import LLMClient
from app.agent.contracts import ToolInvocation
from app.agent.desktop_action_router import DesktopActionRequest, parse_desktop_action
from app.agent.runtime import agent_runtime
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

    @staticmethod
    def _clean_tool_error(error: str | None) -> str:
        cleaned = (error or "The action could not be completed.").strip()
        if cleaned.lower().startswith("tool failed:"):
            cleaned = cleaned[len("tool failed:") :].strip()
        return cleaned

    @staticmethod
    def _desktop_action_success_text(request: DesktopActionRequest, data: dict[str, Any]) -> str:
        subject = request.subject.strip() or "that"

        if request.tool_name == "open_app":
            if data.get("action") == "focused_existing":
                return f"{subject} was already open, so I brought it to the front."
            return f"Opened {subject}."

        if request.tool_name == "focus_app":
            if data.get("focused"):
                return f"Brought {subject} to the front."
            if data.get("raised"):
                return f"Brought {subject} to the front, but Windows kept keyboard focus in the current app."
            reason = str(data.get("reason") or "Windows did not allow the foreground switch").strip()
            if reason.lower() == "app is not running":
                return f"{subject} isn't running, so I couldn't bring it to the front."
            return f"I found {subject}, but I couldn't bring it to the front: {reason}."

        if request.tool_name == "open_path":
            kind = str(data.get("kind") or "item")
            path = str(data.get("path") or subject)
            if kind == "folder":
                return f"Opened the {Path(path).name or subject} folder."
            return f"Opened {Path(path).name or subject}."

        if request.tool_name == "open_url":
            return f"Opened {data.get('url') or subject} in your default browser."

        return "Done."

    async def _handle_desktop_action(self, message: ChatMessage) -> AssistantReply | None:
        request = parse_desktop_action(message.content)
        if request is None:
            return None

        result = await agent_runtime.tools.invoke(
            ToolInvocation(
                tool_name=request.tool_name,
                arguments=request.arguments,
                requested_by="deterministic_desktop_action_router",
            )
        )

        if not result.ok:
            return AssistantReply(
                text=f"I couldn't complete that action: {self._clean_tool_error(result.error)}",
                emotion="concerned",
                should_speak=True,
            )

        return AssistantReply(
            text=self._desktop_action_success_text(request, dict(result.data)),
            emotion="calm",
            should_speak=True,
        )

    async def generate(
        self,
        message: ChatMessage,
        memory_summary: str,
        recent_history: list[str],
        capability_route: CapabilityRoute,
        addressing_instruction: str | None = None,
    ) -> AssistantReply:
        self.last_web_context = None

        desktop_action_reply = await self._handle_desktop_action(message)
        if desktop_action_reply is not None:
            return desktop_action_reply

        decision = self.web_browsing_policy.decide(message.content, capability_route)

        if decision.should_browse and self.web_search_service and self.web_search_service.status.enabled:
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

            if search_results:
                web_user_prompt = self.web_answer_synthesizer.build_web_prompt(message, self.last_web_context)
                return await self._generate_with_provider_error(
                    message,
                    memory_summary,
                    recent_history,
                    capability_route,
                    addressing_instruction=addressing_instruction,
                    system_prompt_override=(
                        "You are Sarah. You perform web-grounded answers when web evidence is provided. "
                        "Stay concise, distinguish current evidence from inference, and be honest about uncertainty."
                    ),
                    user_prompt_override=web_user_prompt,
                )

        return await self._generate_with_provider_error(
            message,
            memory_summary,
            recent_history,
            capability_route,
            addressing_instruction=addressing_instruction,
        )

    async def _generate_with_provider_error(
        self,
        message: ChatMessage,
        memory_summary: str,
        recent_history: list[str],
        capability_route: CapabilityRoute,
        addressing_instruction: str | None = None,
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
                addressing_instruction=addressing_instruction,
                system_prompt_override=system_prompt_override,
                user_prompt_override=user_prompt_override,
            )
        except Exception as exc:
            logger.exception("Primary LLM client failed")
            error_name = type(exc).__name__
            return AssistantReply(
                text=(
                    "I reached the AI provider, but the request failed before I could answer. "
                    f"Provider error: {error_name}. Check the SarahNode terminal for the full details."
                ),
                emotion="concerned",
                should_speak=False,
            )
