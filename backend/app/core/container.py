import logging
from dataclasses import dataclass
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


@dataclass
class ProviderSelection:
    requested: str
    active: str
    mode: str
    reason: str


llm_selection: ProviderSelection | None = None
tts_selection: ProviderSelection | None = None


def build_llm_client() -> LLMClient:
    global llm_selection

    provider = settings.llm_provider.lower()

    if provider == "mock":
        llm_selection = ProviderSelection(provider, "mock", "mock", "Configured explicitly")
        logger.info("LLM provider selected: mock (configured explicitly)")
        return MockLLMClient()

    if provider in {"auto", "openai"}:
        try:
            from app.adapters.llm.openai_client import OpenAIClient

            client = OpenAIClient()
            llm_selection = ProviderSelection(provider, "openai", "real", "API key available")
            logger.info("LLM provider selected: openai (model=%s)", settings.openai_model)
            return client
        except (ImportError, ValueError) as exc:
            reason = str(exc)
            if not settings.openai_api_key:
                logger.warning("OPENAI_API_KEY missing. Falling back to mock LLM.")
            else:
                logger.warning("OpenAI client unavailable. Falling back to mock LLM: %s", reason)

            llm_selection = ProviderSelection(provider, "mock", "mock", reason)
            if provider == "openai":
                logger.warning("OPENAI provider requested but unavailable; using mock mode.")
            return MockLLMClient()

    logger.warning("Unknown llm_provider '%s'. Falling back to local mock.", provider)
    llm_selection = ProviderSelection(provider, "mock", "mock", "Unknown provider")
    return MockLLMClient()


def build_tts_client() -> TTSClient:
    global tts_selection

    provider = settings.tts_provider.lower()

    if provider == "mock":
        tts_selection = ProviderSelection(provider, "mock", "mock", "Configured explicitly")
        logger.info("TTS provider selected: mock (configured explicitly)")
        return MockTTSClient()

    if provider in {"auto", "elevenlabs"}:
        try:
            from app.adapters.tts.elevenlabs_client import ElevenLabsClient

            client = ElevenLabsClient()
            tts_selection = ProviderSelection(provider, "elevenlabs", "real", "API key and voice configured")
            logger.info("TTS provider selected: elevenlabs (model=%s)", settings.elevenlabs_model_id)
            return client
        except (ImportError, ValueError) as exc:
            reason = str(exc)
            if not settings.elevenlabs_api_key:
                logger.warning("ELEVENLABS_API_KEY missing. Falling back to mock TTS.")
            if not settings.elevenlabs_voice_id:
                logger.warning("ELEVENLABS_VOICE_ID missing. Falling back to mock TTS.")

            logger.warning("ElevenLabs unavailable; using mock TTS: %s", reason)
            tts_selection = ProviderSelection(provider, "mock", "mock", reason)
            if provider == "elevenlabs":
                logger.warning("ELEVENLABS provider requested but unavailable; using mock mode.")
            return MockTTSClient()

    logger.warning("Unknown tts_provider '%s'. Falling back to local mock.", provider)
    tts_selection = ProviderSelection(provider, "mock", "mock", "Unknown provider")
    return MockTTSClient()


def provider_status() -> dict[str, dict[str, str]]:
    return {
        "llm": {
            "requested": (llm_selection.requested if llm_selection else settings.llm_provider),
            "active": (llm_selection.active if llm_selection else "mock"),
            "mode": (llm_selection.mode if llm_selection else "mock"),
            "reason": (llm_selection.reason if llm_selection else "Not initialized"),
        },
        "tts": {
            "requested": (tts_selection.requested if tts_selection else settings.tts_provider),
            "active": (tts_selection.active if tts_selection else "mock"),
            "mode": (tts_selection.mode if tts_selection else "mock"),
            "reason": (tts_selection.reason if tts_selection else "Not initialized"),
        },
    }


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
