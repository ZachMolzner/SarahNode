import logging
from pathlib import Path

from app.adapters.avatar.placeholder import PlaceholderAvatarClient
from app.adapters.llm.base import LLMClient
from app.adapters.llm.mock import MockLLMClient
from app.adapters.tts.base import TTSClient
from app.adapters.tts.mock import MockTTSClient
from app.config.settings import settings
from app.memory.state_manager import MemoryManager
from app.orchestration.stream_orchestrator import StreamOrchestrator
from app.safety.moderation import ModerationService
from app.safety.response_policy import ResponsePolicy
from app.services.chat_ingestion import AssistantIntakeService
from app.services.dialogue_engine import DialogueEngine

logger = logging.getLogger(__name__)


def build_llm_client() -> LLMClient:
    provider = settings.llm_provider.lower()

    if provider == "mock":
        return MockLLMClient()

    if provider in {"auto", "openai"}:
        try:
            from app.adapters.llm.openai_client import OpenAIClient

            return OpenAIClient()
        except (ImportError, ValueError) as exc:
            if provider == "openai":
                logger.warning("OPENAI provider requested but unavailable: %s. Falling back to local mock.", exc)
            return MockLLMClient()

    logger.warning("Unknown llm_provider '%s'. Falling back to local mock.", provider)
    return MockLLMClient()


def build_tts_client() -> TTSClient:
    provider = settings.tts_provider.lower()

    if provider == "mock":
        return MockTTSClient()

    if provider in {"auto", "elevenlabs"}:
        try:
            from app.adapters.tts.elevenlabs_client import ElevenLabsClient

            return ElevenLabsClient()
        except (ImportError, ValueError) as exc:
            if provider == "elevenlabs":
                logger.warning("ElevenLabs provider requested but unavailable: %s. Falling back to local mock.", exc)
            return MockTTSClient()

    logger.warning("Unknown tts_provider '%s'. Falling back to local mock.", provider)
    return MockTTSClient()


assistant_intake_service = AssistantIntakeService()
memory_manager = MemoryManager(window_size=settings.assistant_memory_window)
moderation_service = ModerationService()
response_policy = ResponsePolicy()

dialogue_engine = DialogueEngine(
    llm_client=build_llm_client(),
    persona_path=str(Path(__file__).resolve().parents[1] / "config" / "persona.json"),
)

stream_orchestrator = StreamOrchestrator(
    dialogue_engine=dialogue_engine,
    tts_client=build_tts_client(),
    avatar_client=PlaceholderAvatarClient(),
    moderation_service=moderation_service,
    memory_manager=memory_manager,
    response_policy=response_policy,
)
