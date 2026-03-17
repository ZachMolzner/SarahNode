from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.container import assistant_intake_service, memory_manager, stream_orchestrator

router = APIRouter(prefix="/api", tags=["assistant"])


class AssistantMessageRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=500)
    priority: int = Field(default=1, ge=0, le=10)


@router.post("/assistant/messages")
async def send_assistant_message(request: AssistantMessageRequest) -> dict[str, str]:
    message = assistant_intake_service.build_message(
        username=request.username,
        content=request.content,
        priority=request.priority,
    )
    await stream_orchestrator.enqueue_message(message)
    return {"status": "queued"}


@router.post("/chat/send", deprecated=True)
async def send_chat_legacy(request: AssistantMessageRequest) -> dict[str, str]:
    return await send_assistant_message(request)


@router.get("/assistant/state")
def get_assistant_state() -> dict[str, str]:
    return {
        "assistant_state": memory_manager.state.assistant_state,
        "latest_reply": memory_manager.state.last_reply,
        "memory_summary": memory_manager.summarize(),
    }


@router.get("/state", deprecated=True)
def get_state_legacy() -> dict[str, str]:
    return get_assistant_state()
