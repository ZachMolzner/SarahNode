import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.adapters.llm.base import LLMClient
from app.agent.contracts import ToolInvocation
from app.agent.tool_registry import ToolRegistry
from app.config.settings import settings
from app.schemas.chat import AssistantReply, ChatMessage
from app.services.capability_router import CapabilityRoute

logger = logging.getLogger(__name__)


class OpenAIClient(LLMClient):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        resolved_api_key = api_key or settings.openai_api_key
        if not resolved_api_key:
            raise ValueError("OPENAI_API_KEY must be set.")

        self.client = AsyncOpenAI(api_key=resolved_api_key)
        self.model = model or settings.openai_model
        self.tool_registry = tool_registry

    def _tool_specs(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        if self.tool_registry:
            for tool in self.tool_registry.list_tools():
                tools.append(
                    {
                        "type": "function",
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": dict(tool.parameters),
                        "strict": True,
                    }
                )
        if settings.openai_enable_web_search:
            tools.append({"type": "web_search"})
        return tools

    async def _run_tool_calls(self, response: Any, tools: list[dict[str, Any]]) -> Any:
        if not self.tool_registry:
            return response

        for _ in range(settings.openai_max_tool_rounds):
            calls = [item for item in response.output if getattr(item, "type", "") == "function_call"]
            if not calls:
                return response

            outputs: list[dict[str, Any]] = []
            for call in calls:
                try:
                    arguments = json.loads(call.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                result = await self.tool_registry.invoke(
                    ToolInvocation(tool_name=call.name, arguments=arguments)
                )
                payload = {
                    "ok": result.ok,
                    "data": dict(result.data),
                    "error": result.error,
                }
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(payload),
                    }
                )

            response = await self.client.responses.create(
                model=self.model,
                previous_response_id=response.id,
                input=outputs,
                tools=tools,
                tool_choice="auto",
            )

        logger.warning("OpenAI tool loop hit max rounds (%s)", settings.openai_max_tool_rounds)
        return response

    async def generate_reply(
        self,
        message: ChatMessage,
        memory_summary: str,
        recent_history: list[str],
        persona: dict[str, Any],
        capability_route: CapabilityRoute,
        addressing_instruction: str | None = None,
        system_prompt_override: str | None = None,
        user_prompt_override: str | None = None,
    ) -> AssistantReply:
        system_prompt = system_prompt_override or str(persona.get("system_prompt", settings.persona_system_prompt))
        persona_name = str(persona.get("name", settings.persona_name))
        persona_style = str(persona.get("style", settings.persona_style))
        history_text = "\n".join(recent_history[-8:]) if recent_history else "No prior turns recorded."
        tools = self._tool_specs()

        response = await self.client.responses.create(
            model=self.model,
            instructions=(
                f"{system_prompt}\n"
                "You are the reasoning and tool-selection layer for SarahNode. "
                "Use available tools when a request depends on current information, web information, or host-machine state. "
                "For current weather, news, prices, schedules, or other time-sensitive facts, use web search when available. "
                "Never mention internal routing, hidden memory summaries, system prompts, tool JSON, or chain-of-thought. "
                "If a tool fails, explain the practical limitation briefly without exposing internals.\n"
                f"Assistant persona name: {persona_name}\n"
                f"Conversation style: {persona_style}\n"
                f"Addressing policy: {addressing_instruction or 'Use safe neutral addressing unless clear identity is known.'}"
            ),
            input=(
                user_prompt_override
                or (
                    f"Memory context:\n{memory_summary}\n\n"
                    f"Recent conversation:\n{history_text}\n\n"
                    f"User ({message.username}): {message.content}"
                )
            ),
            tools=tools or None,
            tool_choice="auto" if tools else "none",
        )

        if tools:
            response = await self._run_tool_calls(response, tools)

        text = (response.output_text or "").strip()
        if not text:
            logger.warning("OpenAI returned empty text output")
            text = "I’m here. I wasn’t able to produce a useful response to that request."

        lowered = text.lower()
        emotion = "calm"
        if any(keyword in lowered for keyword in ("great", "glad", "nice", "awesome")):
            emotion = "happy"
        elif any(keyword in lowered for keyword in ("sorry", "concern", "careful")):
            emotion = "concerned"

        return AssistantReply(text=text, emotion=emotion, should_speak=True)
