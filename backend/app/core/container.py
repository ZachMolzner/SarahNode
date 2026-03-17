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
from app.services.chat_ingestion import ChatIngestionService
from app.services.dialogue_engine import DialogueEngine


def build_llm_client() -> LLMClient:
    try:
        from app.adapters.llm.openai_client import OpenAIClient

        return OpenAIClient()
    except (ImportError, ValueError):
        return MockLLMClient()


def build_tts_client() -> TTSClient:
    try:
        from app.adapters.tts.elevenlabs_client import ElevenLabsClient

        return ElevenLabsClient()
    except (ImportError, ValueError):
        return MockTTSClient()


chat_ingestion_service = ChatIngestionService()
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
