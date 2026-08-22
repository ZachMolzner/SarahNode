import asyncio
import contextlib
import logging
from typing import Any

from fastapi import WebSocket

from app.adapters.avatar.base import AvatarClient
from app.adapters.tts.base import TTSClient
from app.adapters.tts.mock import MockTTSClient
from app.config.settings import settings
from app.memory.learning import MemoryLearningService
from app.memory.state_manager import MemoryManager
from app.safety.moderation import ModerationService
from app.safety.response_policy import ResponsePolicy
from app.schemas.chat import AssistantReply, ChatMessage
from app.schemas.events import SystemEvent
from app.services.dialogue_engine import DialogueEngine
from app.services.identity_service import IdentityService
from app.services.keyboard_interaction import KeyboardInteractionService
from app.services.screen_awareness import ScreenAwarenessError, ScreenAwarenessService
from app.services.visual_interaction import VisualInteractionService

logger = logging.getLogger(__name__)


class StreamOrchestrator:
    def __init__(
        self,
        dialogue_engine: DialogueEngine,
        tts_client: TTSClient,
        avatar_client: AvatarClient,
        moderation_service: ModerationService,
        memory_manager: MemoryManager,
        response_policy: ResponsePolicy,
        identity_service: IdentityService,
        memory_learning_service: MemoryLearningService,
        screen_awareness_service: ScreenAwarenessService,
        visual_interaction_service: VisualInteractionService,
        keyboard_interaction_service: KeyboardInteractionService,
    ) -> None:
        self.dialogue_engine = dialogue_engine
        self.tts_client = tts_client
        self.avatar_client = avatar_client
        self.moderation_service = moderation_service
        self.memory_manager = memory_manager
        self.response_policy = response_policy
        self.identity_service = identity_service
        self.memory_learning_service = memory_learning_service
        self.screen_awareness_service = screen_awareness_service
        self.visual_interaction_service = visual_interaction_service
        self.keyboard_interaction_service = keyboard_interaction_service

        self.queue: asyncio.PriorityQueue[tuple[int, int, ChatMessage]] | None = None
        self.events: asyncio.Queue[SystemEvent] | None = None
        self._bound_loop: asyncio.AbstractEventLoop | None = None

        self._worker_task: asyncio.Task[None] | None = None
        self._fanout_task: asyncio.Task[None] | None = None

        self._clients_lock = asyncio.Lock()
        self._clients: set[WebSocket] = set()
        self._speech_lock = asyncio.Lock()

        self._cooldown_until = 0.0
        self._sequence = 0

    def _ensure_runtime_queues(self) -> None:
        loop = asyncio.get_running_loop()
        if self._bound_loop is loop and self.queue is not None and self.events is not None:
            return

        self._bound_loop = loop
        self.queue = asyncio.PriorityQueue(maxsize=settings.assistant_max_queue_size)
        self.events = asyncio.Queue()
        self._sequence = 0

    async def start(self) -> None:
        if self._worker_task and not self._worker_task.done():
            return

        self._ensure_runtime_queues()

        for event in await self.avatar_client.initialize():
            await self.emit_event("avatar_event", event)

        await self._set_assistant_state("idle")

        self._worker_task = asyncio.create_task(self._worker_loop(), name="assistant-worker")
        self._fanout_task = asyncio.create_task(self._fanout_loop(), name="assistant-event-broadcaster")

    async def stop(self) -> None:
        tasks = [t for t in (self._worker_task, self._fanout_task) if t is not None]

        for task in tasks:
            task.cancel()

        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task

        self._worker_task = None
        self._fanout_task = None

        async with self._clients_lock:
            clients = list(self._clients)
            self._clients.clear()

        for client in clients:
            with contextlib.suppress(Exception):
                await client.close()

    async def register_ws(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._clients_lock:
            self._clients.add(websocket)

    async def unregister_ws(self, websocket: WebSocket) -> None:
        async with self._clients_lock:
            self._clients.discard(websocket)

    async def enqueue_message(self, message: ChatMessage) -> None:
        self._ensure_runtime_queues()
        assert self.queue is not None

        self.memory_manager.add_message(message)

        self._sequence += 1
        await self.queue.put((-message.priority, self._sequence, message))

        await self.emit_event(
            "chat_received",
            {
                "username": message.username,
                "content": message.content,
                "priority": message.priority,
                "source": message.source.value,
                "conversation_mode": message.conversation_mode,
            },
        )

    async def emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self._ensure_runtime_queues()
        assert self.events is not None
        await self.events.put(SystemEvent(type=event_type, payload=payload))

    async def _fanout_loop(self) -> None:
        while True:
            assert self.events is not None
            event = await self.events.get()

            try:
                async with self._clients_lock:
                    clients = list(self._clients)

                stale: list[WebSocket] = []

                for client in clients:
                    try:
                        await client.send_json(event.model_dump(mode="json"))
                    except Exception:
                        stale.append(client)

                if stale:
                    async with self._clients_lock:
                        for client in stale:
                            self._clients.discard(client)

            finally:
                assert self.events is not None
                self.events.task_done()

    async def _worker_loop(self) -> None:
        while True:
            assert self.queue is not None
            _priority, _sequence, message = await self.queue.get()

            try:
                await self._process_message(message)
            except Exception as exc:
                logger.exception("Worker failure")

                await self._set_assistant_state("error")
                await self.emit_event(
                    "error",
                    {
                        "stage": "worker",
                        "username": message.username,
                        "details": str(exc),
                    },
                )
                await self._set_assistant_state("idle")

            finally:
                assert self.queue is not None
                self.queue.task_done()

    async def _process_message(self, message: ChatMessage) -> None:
        now = asyncio.get_running_loop().time()

        if now < self._cooldown_until:
            await asyncio.sleep(self._cooldown_until - now)

        await self._set_assistant_state("thinking")

        moderation = self.moderation_service.evaluate(message)
        await self.emit_event("moderation_decision", moderation.model_dump())

        speaker_identity = self.identity_service.resolve_speaker(username=message.username)
        addressing_context = self.identity_service.addressing_context(
            speaker=speaker_identity,
            conversation_mode=message.conversation_mode,
            turn_index=self._sequence,
        )
        self.memory_manager.set_last_identity(
            speaker_id=speaker_identity.speaker_id,
            confidence=speaker_identity.confidence,
            address_name=addressing_context.address_name,
            address_mode=addressing_context.mode,
        )
        await self.emit_event(
            "identity_resolution",
            {
                "speaker_id": speaker_identity.speaker_id,
                "confidence": speaker_identity.confidence,
                "high_confidence": speaker_identity.is_high_confidence,
                "address_name": addressing_context.address_name,
                "address_mode": addressing_context.mode,
                "rule": addressing_context.deterministic_rule,
            },
        )

        session_memory = self.memory_manager.summarize()
        memory_scopes = {"household"}
        if speaker_identity.speaker_id != "unknown":
            memory_scopes.add(speaker_identity.speaker_id)
        persistent_memory = self.memory_learning_service.context_for(
            message.content,
            scopes=memory_scopes,
            limit=8,
        )
        memory_summary = (
            f"Recent conversation memory:\n{session_memory}\n\n"
            f"Relevant persistent memory:\n{persistent_memory}"
        )
        await self.emit_event(
            "memory_retrieval",
            {
                "speaker_id": speaker_identity.speaker_id,
                "scopes": sorted(memory_scopes),
                "has_persistent_context": persistent_memory != "No relevant persistent memories.",
            },
        )

        explicit_memory_decision = None
        explicit_memory_classifier = getattr(self.memory_learning_service, "classify_explicit_memory_request", None)
        if callable(explicit_memory_classifier):
            explicit_memory_decision = explicit_memory_classifier(message.content)

        recent_history = self.memory_manager.recent_history()
        capability_route = self.dialogue_engine.classify_capability(message)
        self.memory_manager.set_last_capability(capability_route.intent)
        await self.emit_event(
            "capability_routing",
            {
                "intent": capability_route.intent,
                "confidence": capability_route.confidence,
                "requires_web_lookup": capability_route.requires_web_lookup,
            },
        )
        generated_reply = None

        if moderation.allowed:
            keyboard_interaction_requested = self.keyboard_interaction_service.can_handle(message)
            visual_interaction_requested = self.visual_interaction_service.can_handle(message)

            # Pending Enter and pending visual actions are deliberately ephemeral and
            # mutually exclusive in practice. Any unrelated turn invalidates the old
            # confirmation so a stale approval cannot act on a changed desktop.
            if self.keyboard_interaction_service.has_pending(message.user_id) and not keyboard_interaction_requested:
                cancelled_keyboard = self.keyboard_interaction_service.cancel_pending(message.user_id)
                if cancelled_keyboard is not None:
                    await self.emit_event(
                        "keyboard_interaction_invalidated",
                        {
                            "key": "enter",
                            "window": cancelled_keyboard.title,
                            "reason": "intervening_user_message",
                        },
                    )

            if self.visual_interaction_service.has_pending(message.user_id) and not visual_interaction_requested:
                cancelled_visual = self.visual_interaction_service.cancel_pending(message.user_id)
                if cancelled_visual is not None:
                    await self.emit_event(
                        "visual_interaction_invalidated",
                        {
                            "target": cancelled_visual.target_query,
                            "reason": "intervening_user_message",
                        },
                    )

            explicit_status = getattr(explicit_memory_decision, "status", None)
            if explicit_status == "blocked_secret":
                self.dialogue_engine.last_web_context = None
                generated_reply = AssistantReply(
                    text=(
                        "I won't store passwords, API keys, access tokens, recovery codes, private keys, "
                        "or other credentials in persistent memory. The credential value was also omitted from my rolling session memory."
                    ),
                    emotion="calm",
                    should_speak=True,
                )
            elif explicit_status == "safe_memory":
                self.dialogue_engine.last_web_context = None
                generated_reply = AssistantReply(
                    text="Saved that to persistent memory.",
                    emotion="calm",
                    should_speak=True,
                )
            elif keyboard_interaction_requested:
                self.dialogue_engine.last_web_context = None
                other_pending = bool(
                    self.dialogue_engine.pending_confirmed_actions.get(message.user_id)
                    or self.dialogue_engine.pending_action_plans.get(message.user_id)
                )
                await self.emit_event(
                    "keyboard_interaction_started",
                    {
                        "persistence": "ephemeral",
                        "other_system_change_pending": other_pending,
                    },
                )
                try:
                    generated_reply = await self.keyboard_interaction_service.handle(
                        message,
                        other_system_change_pending=other_pending,
                    )
                    await self.emit_event(
                        "keyboard_interaction_completed",
                        {
                            "pending_enter": self.keyboard_interaction_service.has_pending(message.user_id),
                        },
                    )
                except Exception as exc:
                    logger.exception("Controlled keyboard interaction failed")
                    generated_reply = AssistantReply(
                        text=f"I couldn't complete that controlled keyboard interaction safely: {exc}",
                        emotion="concerned",
                        should_speak=True,
                    )
                    await self.emit_event(
                        "error",
                        {
                            "stage": "keyboard_interaction",
                            "username": message.username,
                            "details": str(exc),
                        },
                    )
            elif visual_interaction_requested:
                self.dialogue_engine.last_web_context = None
                other_pending = bool(
                    self.dialogue_engine.pending_confirmed_actions.get(message.user_id)
                    or self.dialogue_engine.pending_action_plans.get(message.user_id)
                )
                await self.emit_event(
                    "visual_interaction_started",
                    {
                        "persistence": "ephemeral",
                        "other_system_change_pending": other_pending,
                    },
                )
                try:
                    generated_reply = await self.visual_interaction_service.handle(
                        message,
                        other_system_change_pending=other_pending,
                    )
                    await self.emit_event(
                        "visual_interaction_completed",
                        {
                            "pending_visual_action": self.visual_interaction_service.has_pending(message.user_id),
                        },
                    )
                except Exception as exc:
                    logger.exception("Visual interaction failed")
                    generated_reply = AssistantReply(
                        text=f"I couldn't complete that visual interaction safely: {exc}",
                        emotion="concerned",
                        should_speak=True,
                    )
                    await self.emit_event(
                        "error",
                        {
                            "stage": "visual_interaction",
                            "username": message.username,
                            "details": str(exc),
                        },
                    )
            elif self.screen_awareness_service.should_handle(message.content):
                # Screen requests bypass the text-model/tool loop. Capture happens only
                # for this explicit turn and the image is never added to memory/history.
                self.dialogue_engine.last_web_context = None
                await self.emit_event(
                    "screen_capture_started",
                    {
                        "mode": "explicit_request",
                        "persistence": "ephemeral_in_memory",
                    },
                )
                try:
                    visual = await self.screen_awareness_service.analyze(message.content)
                    generated_reply = AssistantReply(
                        text=visual.text,
                        emotion="calm",
                        should_speak=True,
                    )
                    await self.emit_event(
                        "screen_analysis_completed",
                        {
                            "model": visual.model,
                            "reasoning_mode": visual.reasoning_mode,
                            "target_count": len(visual.targets),
                            "source_width": visual.source_width,
                            "source_height": visual.source_height,
                            "sent_width": visual.sent_width,
                            "sent_height": visual.sent_height,
                            "sarah_hidden_for_capture": visual.sarah_hidden_for_capture,
                            "screenshot_persisted": False,
                        },
                    )
                except ScreenAwarenessError as exc:
                    generated_reply = AssistantReply(
                        text=str(exc),
                        emotion="concerned",
                        should_speak=True,
                    )
                    await self.emit_event(
                        "error",
                        {
                            "stage": "screen_awareness",
                            "username": message.username,
                            "details": str(exc),
                        },
                    )
            else:
                generated_reply = await self.dialogue_engine.generate(
                    message,
                    memory_summary,
                    recent_history,
                    capability_route,
                    addressing_instruction=(
                        f"Deterministic identity: speaker={speaker_identity.speaker_id}, "
                        f"confidence={speaker_identity.confidence:.2f}, mode={addressing_context.mode}. "
                        f"Address as '{addressing_context.address_name}'. "
                        f"Tone directive: {addressing_context.tone_directive} "
                        "Use persistent memory when relevant, but never claim a memory that was not supplied or retrieved. "
                        "Only call memory_remember when the user explicitly asks you to remember/save/learn something. "
                        "If speaker is unknown, use neutral greetings like 'Hey there' or 'How can I help?'. "
                        "Do not invent nicknames. Never repeat 'Mama' more than once in a response."
                    ),
                )

        web_context = self.dialogue_engine.last_web_context
        used_live_web = bool(web_context and web_context.checked_web)
        web_sources = web_context.source_metadata() if web_context else []
        self.memory_manager.set_last_web_usage(used_live_web, web_sources)
        if web_context:
            await self.emit_event(
                "web_search_completed",
                {
                    "provider": web_context.provider,
                    "source_count": len(web_context.search_results),
                    "fetched_page_count": len(web_context.fetched_pages),
                    "decision_reason": web_context.decision_reason,
                },
            )

        reply = self.response_policy.apply(moderation, generated_reply)

        if web_context:
            distilled_points = [
                result.snippet.strip()
                for result in web_context.search_results
                if result.snippet.strip()
            ]
            await self.emit_event(
                "web_grounded_answer",
                {
                    "title": message.content[:120],
                    "bullets": distilled_points[:5],
                    "sources": [
                        {
                            "title": source.get("title", ""),
                            "url": source.get("url") or source.get("link") or source.get("href"),
                        }
                        for source in web_sources
                        if source.get("title")
                    ],
                    "provider": web_context.provider,
                },
            )
        self.memory_manager.set_last_reply(reply.text)

        await self.emit_event("reply_selected", reply.model_dump())

        expression_event = await self.avatar_client.dispatch(
            "expression_change",
            {"expression": reply.emotion},
        )
        await self.emit_event("avatar_event", expression_event)

        if reply.should_speak:
            async with self._speech_lock:
                await self._set_assistant_state("speaking")

                await self.emit_event(
                    "speaking_status",
                    {"is_speaking": True, "emotion": reply.emotion},
                )

                avatar_start = await self.avatar_client.dispatch(
                    "speaking_start",
                    {"text": reply.text, "emotion": reply.emotion},
                )
                await self.emit_event("avatar_event", avatar_start)

                try:
                    tts_result = await self.tts_client.synthesize(reply.text)
                    await self.emit_event("tts_output", tts_result)

                    duration = float(tts_result.get("duration_seconds", 0.0) or 0.0)
                    if duration > 0:
                        await asyncio.sleep(duration)
                except Exception as exc:
                    logger.exception("TTS generation failed, using mock fallback")
                    await self.emit_event(
                        "error",
                        {
                            "stage": "tts",
                            "username": message.username,
                            "details": str(exc),
                        },
                    )
                    tts_result = await MockTTSClient().synthesize(reply.text)
                    await self.emit_event("tts_output", tts_result)

                avatar_stop = await self.avatar_client.dispatch("speaking_stop", {})
                await self.emit_event("avatar_event", avatar_stop)

                await self.emit_event(
                    "speaking_status",
                    {"is_speaking": False, "emotion": "idle"},
                )

        await self._set_assistant_state("idle")

        self._cooldown_until = (
            asyncio.get_running_loop().time() + settings.assistant_cooldown_seconds
        )

    async def _set_assistant_state(self, assistant_state: str) -> None:
        self.memory_manager.set_assistant_state(assistant_state)

        await self.emit_event("assistant_state", {"state": assistant_state})

        avatar_event = await self.avatar_client.dispatch(
            "state_change",
            {"state": assistant_state},
        )
        await self.emit_event("avatar_event", avatar_event)
