from fastapi import APIRouter

from app.core.container import chat_ingestion_service, memory_manager, stream_orchestrator
from app.schemas.chat import ChatMessage

router = APIRouter(prefix="/api", tags=["control"])


@router.post("/mock-chat")
async def post_mock_chat(message: ChatMessage) -> dict[str, str]:
    await stream_orchestrator.enqueue_message(message)
    return {"status": "queued"}


@router.post("/mock-chat/simple")
async def post_simple_chat(username: str, content: str, priority: int = 1) -> dict[str, str]:
    msg = chat_ingestion_service.mock_message(username=username, content=content, priority=priority)
    await stream_orchestrator.enqueue_message(msg)
    return {"status": "queued"}


@router.get("/memory-summary")
def get_memory_summary() -> dict[str, str]:
    return {"summary": memory_manager.summarize()}
