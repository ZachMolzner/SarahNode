import asyncio
import contextlib
import logging
from typing import Any

from fastapi import WebSocket

from app.adapters.avatar.base import AvatarClient
from app.adapters.tts.base import TTSClient
from app.adapters.tts.mock import MockTTSClient
from app.config.settings import settings
from app.memory.state_manager import MemoryManager
from app.safety.moderation import ModerationService
from app.safety.response_policy import ResponsePolicy
from app.schemas.chat import ChatMessage
from app.schemas.events import SystemEvent
from app.services.dialogue_engine import DialogueEngine

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
    ) -> None:
        self.dialogue_engine = dialogue_engine
        self.tts_client = tts_client
        self.avatar_client = avatar_client
        self.moderation_service = moderation_service
        self.memory_manager = memory_manager
        self.response_policy = response_policy

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

        # Initialize avatar
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

        # Moderation
        moderation = self.moderation_service.evaluate(message)
        await self.emit_event("moderation_decision", moderation.model_dump())

        # Dialogue
        memory_summary = self.memory_manager.summarize()
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
            generated_reply = await self.dialogue_engine.generate(message, memory_summary, recent_history, capability_route)

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
        self.memory_manager.set_last_reply(reply.text)

        await self.emit_event("reply_selected", reply.model_dump())

        # Avatar emotion
        expression_event = await self.avatar_client.dispatch(
            "expression_change",
            {"expression": reply.emotion},
        )
        await self.emit_event("avatar_event", expression_event)

        # Speaking + TTS
        if reply.should_speak:
            async with self._speech_lock:
                await self._set_assistant_state("speaking")

                # START speaking
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

                # STOP speaking
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
