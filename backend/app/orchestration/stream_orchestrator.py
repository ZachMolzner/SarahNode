import asyncio
import contextlib
import logging
from typing import Any

from fastapi import WebSocket

from app.adapters.avatar.base import AvatarClient
from app.adapters.tts.base import TTSClient
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

        self.queue: asyncio.PriorityQueue[tuple[int, int, ChatMessage]] = asyncio.PriorityQueue(
            maxsize=settings.assistant_max_queue_size
        )
        self.events: asyncio.Queue[SystemEvent] = asyncio.Queue()

        self._worker_task: asyncio.Task[None] | None = None
        self._fanout_task: asyncio.Task[None] | None = None

        self._clients_lock = asyncio.Lock()
        self._clients: set[WebSocket] = set()
        self._speech_lock = asyncio.Lock()

        self._cooldown_until = 0.0
        self._sequence = 0

    async def start(self) -> None:
        if self._worker_task and not self._worker_task.done():
            return

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
        await self.events.put(SystemEvent(type=event_type, payload=payload))

    async def _fanout_loop(self) -> None:
        while True:
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
                self.events.task_done()

    async def _worker_loop(self) -> None:
        while True:
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
        generated_reply = None

        if moderation.allowed:
            generated_reply = await self.dialogue_engine.generate(message, memory_summary)

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

                tts_result = await self.tts_client.synthesize(reply.text)
                await self.emit_event("tts_output", tts_result)

                duration = float(tts_result.get("duration_seconds", 0.0) or 0.0)
                if duration > 0:
                    await asyncio.sleep(duration)

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
