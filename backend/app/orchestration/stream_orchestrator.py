import asyncio
import logging
from typing import Any

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
        self.queue: asyncio.PriorityQueue[tuple[int, ChatMessage]] = asyncio.PriorityQueue(settings.assistant_max_queue_size)
        self.events: asyncio.Queue[SystemEvent] = asyncio.Queue()
        self._worker_task: asyncio.Task[Any] | None = None
        self._speech_lock = asyncio.Lock()
        self._cooldown_until = 0.0

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker(), name="stream-orchestrator-worker")

    async def stop(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            self._worker_task = None

    async def enqueue_message(self, message: ChatMessage) -> None:
        self.memory_manager.add_message(message)
        await self.queue.put((-message.priority, message))
        await self.events.put(SystemEvent(type="chat_received", payload={"username": message.username, "content": message.content}))

    async def _worker(self) -> None:
        while True:
            _, message = await self.queue.get()
            now = asyncio.get_running_loop().time()
            if now < self._cooldown_until:
                await asyncio.sleep(self._cooldown_until - now)

            moderation = self.moderation_service.evaluate(message)
            await self.events.put(SystemEvent(type="moderation_decision", payload=moderation.model_dump()))

            memory_summary = self.memory_manager.summarize()
            generated = None
            if moderation.allowed:
                generated = await self.dialogue_engine.generate(message, memory_summary)
            reply = self.response_policy.apply(moderation, generated)
            await self.events.put(SystemEvent(type="reply_selected", payload=reply.model_dump()))

            if reply.should_speak:
                async with self._speech_lock:
                    await self.avatar_client.dispatch("talking_start", {"emotion": reply.emotion})
                    await self.events.put(SystemEvent(type="speaking_status", payload={"is_speaking": True, "emotion": reply.emotion}))
                    tts_result = await self.tts_client.synthesize(reply.text)
                    await self.events.put(SystemEvent(type="tts_output", payload=tts_result))
                    await asyncio.sleep(tts_result["duration_seconds"])
                    await self.avatar_client.dispatch("talking_stop")
                    await self.events.put(SystemEvent(type="speaking_status", payload={"is_speaking": False, "emotion": "idle"}))

            self._cooldown_until = asyncio.get_running_loop().time() + settings.assistant_cooldown_seconds
            logger.info("Processed message from %s", message.username)
