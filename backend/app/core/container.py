from app.adapters.avatar.mock import MockAvatarClient
from app.adapters.llm.mock import MockLLMClient
from app.adapters.tts.mock import MockTTSClient
from app.config.settings import settings
from app.memory.state_manager import MemoryManager
from app.orchestration.stream_orchestrator import StreamOrchestrator
from app.safety.moderation import ModerationService
from app.safety.response_policy import ResponsePolicy
from app.services.chat_ingestion import ChatIngestionService
from app.services.dialogue_engine import DialogueEngine

chat_ingestion_service = ChatIngestionService()
dialogue_engine = DialogueEngine(llm_client=MockLLMClient(), persona_path="app/config/persona.json")
memory_manager = MemoryManager(window_size=settings.assistant_memory_window)
moderation_service = ModerationService()
response_policy = ResponsePolicy()
stream_orchestrator = StreamOrchestrator(
    dialogue_engine=dialogue_engine,
    tts_client=MockTTSClient(),
    avatar_client=MockAvatarClient(),
    moderation_service=moderation_service,
    memory_manager=memory_manager,
    response_policy=response_policy,
)
