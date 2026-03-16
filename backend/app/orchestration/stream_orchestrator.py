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

        self._speech_lock = asyncio.Lock()
        self._clients_lock = asyncio.Lock()
        self._clients: set[WebSocket] = set()

        self._cooldown_until = 0.0
        self._sequence = 0

    async def start(self) -> None:
        if self._worker_task and not self._worker_task.done():
            return

        self._worker_task = asyncio.create_task(
            self._worker_loop(),
            name="stream-orchestrator-worker",
        )
        self._fanout_task = asyncio.create_task(
            self._fanout_loop(),
            name="event-broadcaster",
        )

    async def stop(self) -> None:
        tasks = [task for task in (self._worker_task, self._fanout_task) if task is not None]

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

                logger.debug("Emitted event: %s", event.type)
            finally:
                self.events.task_done()

    async def _worker_loop(self) -> None:
        while True:
            _priority, _sequence, message = await self.queue.get()

            try:
                await self._process_message(message)
            except Exception:
                logger.exception("Unexpected worker error while processing message")
                await self.emit_event(
                    "error",
                    {
                        "stage": "worker",
                        "username": message.username,
                        "details": "Internal worker error.",
                    },
                )
            finally:
                self.queue.task_done()

    async def _process_message(self, message: ChatMessage) -> None:
        now = asyncio.get_running_loop().time()
        if now < self._cooldown_until:
            await asyncio.sleep(self._cooldown_until - now)

        moderation = self.moderation_service.evaluate(message)
        await self.emit_event("moderation_decision", moderation.model_dump())

        memory_summary = self.memory_manager.summarize()
        generated_reply = None

        if moderation.allowed:
            generated_reply = await self.dialogue_engine.generate(message, memory_summary)

        reply = self.response_policy.apply(moderation, generated_reply)
        await self.emit_event("reply_selected", reply.model_dump())

        if reply.should_speak:
            async with self._speech_lock:
                await self.avatar_client.dispatch("talking_start", {"emotion": reply.emotion})
                await self.emit_event(
                    "avatar_event",
                    {"event_type": "talking_start", "emotion": reply.emotion},
                )
                await self.emit_event(
                    "speaking_status",
                    {"is_speaking": True, "emotion": reply.emotion},
                )

                tts_result = await self.tts_client.synthesize(reply.text)
                await self.emit_event("tts_output", tts_result)

                await asyncio.sleep(float(tts_result.get("duration_seconds", 0.0)))

                await self.avatar_client.dispatch("talking_stop", {"emotion": "idle"})
                await self.emit_event(
                    "avatar_event",
                    {"event_type": "talking_stop", "emotion": "idle"},
                )
                await self.emit_event(
                    "speaking_status",
                    {"is_speaking": False, "emotion": "idle"},
                )

        self._cooldown_until = (
            asyncio.get_running_loop().time() + settings.assistant_cooldown_seconds
        )

        logger.info("Processed message from %s", message.username)
