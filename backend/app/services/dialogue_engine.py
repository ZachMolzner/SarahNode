import json
import logging
from pathlib import Path
from typing import Any

from app.adapters.llm.base import LLMClient
from app.agent.batch_action_router import (
    ActionPlan,
    PendingActionPlanStore,
    PlannedAction,
    parse_action_plan,
)
from app.agent.confirmed_action_router import (
    ConfirmedActionRequest,
    PendingConfirmedActionStore,
    is_cancellation,
    is_confirmation,
    parse_confirmed_action,
)
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
        self.pending_confirmed_actions = PendingConfirmedActionStore(ttl_seconds=180)
        self.pending_action_plans = PendingActionPlanStore(ttl_seconds=180)

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

    @staticmethod
    def _confirmed_action_success_text(request: ConfirmedActionRequest, data: dict[str, Any]) -> str:
        if request.tool_name == "create_folder":
            return f"Confirmed. Created the folder {data.get('path')}."

        if request.tool_name == "create_file":
            return f"Confirmed. Created the file {data.get('path')}."

        if request.tool_name == "move_path":
            return f"Confirmed. Moved it to {data.get('destination')}."

        if request.tool_name == "recycle_path":
            return f"Confirmed. Moved {data.get('path')} to the Recycle Bin."

        if request.tool_name == "close_app":
            action = str(data.get("action") or "")
            app = str(data.get("app") or request.arguments.get("app") or "the app")
            if action == "already_closed":
                return f"{app} is already closed."
            if action == "closed":
                remaining = int(data.get("remaining_processes", 0) or 0)
                if remaining:
                    return f"Confirmed. Closed {app}. {remaining} background process(es) remain without a visible window."
                return f"Confirmed. Closed {app}."
            if action == "close_incomplete":
                reason = str(data.get("reason") or "The app stayed open.")
                return f"I sent {app} a normal close request, but it stayed open: {reason}"
            if action == "close_requested":
                windows = int(data.get("windows_signaled", 0) or 0)
                return f"Confirmed. Asked {app} to close normally ({windows} window(s))."
            reason = str(data.get("reason") or "I couldn't close it safely.")
            return f"I found {app}, but I didn't force-close it: {reason}."

        if request.tool_name == "terminate_app":
            action = str(data.get("action") or "")
            app = str(data.get("app") or request.arguments.get("app") or "the app")
            if action == "already_closed":
                return f"{app} is already closed."
            if action == "terminated":
                count = int(data.get("terminated", 0) or 0)
                return f"Confirmed. Force-closed {app} and terminated {count} matching process(es)."
            remaining = int(data.get("remaining_processes", 0) or 0)
            reason = str(data.get("reason") or "Some processes could not be terminated.")
            return f"I tried to force-close {app}, but {remaining} matching process(es) remain: {reason}."

        return "Confirmed. Done."

    @staticmethod
    def _short_summary(summary: str, limit: int = 120) -> str:
        compact = " ".join(summary.split())
        return compact if len(compact) <= limit else compact[: limit - 3] + "..."

    def _planned_action_success_text(self, action: PlannedAction, data: dict[str, Any]) -> str:
        if action.kind == "desktop":
            request = DesktopActionRequest(
                tool_name=action.tool_name,
                arguments=action.arguments,
                subject=action.subject,
            )
            return self._desktop_action_success_text(request, data)

        request = ConfirmedActionRequest(
            tool_name=action.tool_name,
            arguments=action.arguments,
            summary=action.summary,
        )
        text = self._confirmed_action_success_text(request, data)
        if text.startswith("Confirmed. "):
            text = text[len("Confirmed. ") :]
        return text

    @staticmethod
    def _logical_action_failure(action: PlannedAction, data: dict[str, Any]) -> str | None:
        state = str(data.get("action") or "")
        if action.tool_name == "close_app" and state == "close_incomplete":
            return str(data.get("reason") or "The app stayed open")
        if action.tool_name == "terminate_app" and state == "terminate_incomplete":
            return str(data.get("reason") or "Some app processes are still running")
        return None

    async def _execute_action_plan(self, plan: ActionPlan, *, confirmed: bool) -> AssistantReply:
        completed: list[str] = []
        total = len(plan.actions)

        for index, action in enumerate(plan.actions, start=1):
            result = await agent_runtime.tools.invoke(
                ToolInvocation(
                    tool_name=action.tool_name,
                    arguments=action.arguments,
                    requested_by="confirmed_batch_action_router" if confirmed else "batch_action_router",
                ),
                confirmed=confirmed,
            )
            if not result.ok:
                error = self._clean_tool_error(result.error)
                prefix = f"Completed {len(completed)} of {total} tasks. " if completed else ""
                return AssistantReply(
                    text=f"{prefix}Step {index} failed: {error}. Remaining steps were not run.",
                    emotion="concerned",
                    should_speak=True,
                )

            data = dict(result.data)
            logical_failure = self._logical_action_failure(action, data)
            if logical_failure:
                prefix = f"Completed {len(completed)} of {total} tasks. " if completed else ""
                return AssistantReply(
                    text=f"{prefix}Step {index} did not complete: {logical_failure}. Remaining steps were not run.",
                    emotion="concerned",
                    should_speak=True,
                )

            completed.append(self._planned_action_success_text(action, data))

        lines = [f"{index}. {text}" for index, text in enumerate(completed, start=1)]
        return AssistantReply(
            text=f"Completed all {total} tasks:\n" + "\n".join(lines),
            emotion="calm",
            should_speak=True,
        )

    async def _handle_batch_action(self, message: ChatMessage) -> AssistantReply | None:
        pending_batch = self.pending_action_plans.get(message.user_id)

        if pending_batch is not None and is_cancellation(message.content):
            self.pending_action_plans.cancel(message.user_id)
            return AssistantReply(
                text=f"Cancelled the pending {len(pending_batch.plan.actions)}-task plan. Nothing from that plan was run.",
                emotion="calm",
                should_speak=True,
            )

        if pending_batch is not None and is_confirmation(message.content):
            pending_batch = self.pending_action_plans.pop(message.user_id)
            if pending_batch is None:
                return AssistantReply(
                    text="That batch confirmation expired. Please request the tasks again.",
                    emotion="concerned",
                    should_speak=True,
                )
            return await self._execute_action_plan(pending_batch.plan, confirmed=True)

        try:
            plan = parse_action_plan(message.content)
        except Exception as exc:
            logger.info("Multi-action request rejected during planning: %s", exc)
            return AssistantReply(
                text=f"I can't run that multi-task request safely: {self._clean_tool_error(str(exc))}",
                emotion="concerned",
                should_speak=True,
            )

        if plan is None:
            if pending_batch is not None:
                try:
                    new_confirmed = parse_confirmed_action(message.content)
                except Exception:
                    new_confirmed = None
                if new_confirmed is not None:
                    return AssistantReply(
                        text=(
                            f"You already have a pending {len(pending_batch.plan.actions)}-task plan. "
                            'Reply "confirm" or "cancel" before staging another system change.'
                        ),
                        emotion="concerned",
                        should_speak=True,
                    )
            return None

        if plan.requires_confirmation:
            existing_single = self.pending_confirmed_actions.get(message.user_id)
            if existing_single is not None:
                return AssistantReply(
                    text='You already have a pending system change. Reply "confirm" or "cancel" before staging a multi-task plan.',
                    emotion="concerned",
                    should_speak=True,
                )

            self.pending_action_plans.stage(message.user_id, plan)
            plan_lines = [
                f"{index}. {self._short_summary(action.summary)}"
                for index, action in enumerate(plan.actions, start=1)
            ]
            return AssistantReply(
                text=(
                    f"I staged {len(plan.actions)} tasks. Because at least one changes your system, none have run yet:\n"
                    + "\n".join(plan_lines)
                    + '\nReply "confirm" within 3 minutes to run the whole plan in order, or "cancel".'
                ),
                emotion="concerned",
                should_speak=True,
            )

        return await self._execute_action_plan(plan, confirmed=False)

    async def _handle_confirmed_action(self, message: ChatMessage) -> AssistantReply | None:
        pending = self.pending_confirmed_actions.get(message.user_id)

        if pending is not None and is_cancellation(message.content):
            self.pending_confirmed_actions.cancel(message.user_id)
            return AssistantReply(
                text=f"Cancelled. I did not {pending.request.summary}.",
                emotion="calm",
                should_speak=True,
            )

        if pending is not None and is_confirmation(message.content):
            pending = self.pending_confirmed_actions.pop(message.user_id)
            if pending is None:
                return AssistantReply(
                    text="That confirmation expired. Please request the action again.",
                    emotion="concerned",
                    should_speak=True,
                )

            result = await agent_runtime.tools.invoke(
                ToolInvocation(
                    tool_name=pending.request.tool_name,
                    arguments=pending.request.arguments,
                    requested_by="confirmed_desktop_action_router",
                ),
                confirmed=True,
            )
            if not result.ok:
                return AssistantReply(
                    text=f"I didn't make the change: {self._clean_tool_error(result.error)}",
                    emotion="concerned",
                    should_speak=True,
                )
            return AssistantReply(
                text=self._confirmed_action_success_text(pending.request, dict(result.data)),
                emotion="calm",
                should_speak=True,
            )

        request: ConfirmedActionRequest | None
        try:
            request = parse_confirmed_action(message.content)
        except Exception as exc:
            logger.info("Phase 4C request rejected during preview: %s", exc)
            return AssistantReply(
                text=f"I can't stage that change safely: {self._clean_tool_error(str(exc))}",
                emotion="concerned",
                should_speak=True,
            )

        if request is not None:
            self.pending_confirmed_actions.stage(message.user_id, request)
            return AssistantReply(
                text=(
                    f"This will {request.summary}. Nothing has changed yet. "
                    'Reply "confirm" within 3 minutes to proceed, or "cancel".'
                ),
                emotion="concerned",
                should_speak=True,
            )

        if pending is None and is_confirmation(message.content):
            return AssistantReply(
                text="There isn't a pending system change to confirm.",
                emotion="calm",
                should_speak=True,
            )

        if pending is None and is_cancellation(message.content):
            return AssistantReply(
                text="There isn't a pending system change to cancel.",
                emotion="calm",
                should_speak=True,
            )

        return None

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

        batch_action_reply = await self._handle_batch_action(message)
        if batch_action_reply is not None:
            return batch_action_reply

        confirmed_action_reply = await self._handle_confirmed_action(message)
        if confirmed_action_reply is not None:
            return confirmed_action_reply

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
