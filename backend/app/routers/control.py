import logging

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.container import (
    assistant_intake_service,
    memory_manager,
    provider_status,
    stream_orchestrator,
    voice_service,
)

logger = logging.getLogger(__name__)

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




class VoiceEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)


@router.post("/assistant/voice/event")
async def emit_voice_event(request: VoiceEventRequest) -> dict[str, str]:
    if not request.event_type.startswith("voice:"):
        raise HTTPException(status_code=400, detail="event_type must start with 'voice:'")

    await stream_orchestrator.emit_event(request.event_type, {})
    return {"status": "ok"}


@router.post("/assistant/transcribe")
async def transcribe_audio(request: Request) -> dict[str, object]:
    try:
        form = await request.form()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Expected multipart/form-data with a file field.") from exc

    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise HTTPException(status_code=400, detail="Missing audio file in 'file' form field.")

    await stream_orchestrator.emit_event(
        "voice:recording_stopped",
        {"filename": upload.filename, "content_type": upload.content_type},
    )
    await stream_orchestrator.emit_event("voice:transcribing", {"filename": upload.filename})

    try:
        result = await voice_service.transcribe_upload(upload)
    except RuntimeError as exc:
        await stream_orchestrator.emit_event("voice:error", {"stage": "configuration", "details": str(exc)})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Transcription failed")
        await stream_orchestrator.emit_event("voice:error", {"stage": "transcription", "details": str(exc)})
        raise HTTPException(status_code=500, detail="Transcription failed.") from exc

    await stream_orchestrator.emit_event(
        "voice:transcribed",
        {
            "text": result.get("text", ""),
            "provider": result.get("provider", {}),
            "duration_ms": result.get("duration_ms", 0),
        },
    )
    return result


@router.post("/chat/send", deprecated=True)
async def send_chat_legacy(request: AssistantMessageRequest) -> dict[str, str]:
    return await send_assistant_message(request)


@router.get("/assistant/state")
def get_assistant_state() -> dict[str, object]:
    return {
        "assistant_state": memory_manager.state.assistant_state,
        "latest_reply": memory_manager.state.last_reply,
        "memory_summary": memory_manager.summarize(),
        "providers": provider_status(),
    }


@router.get("/state", deprecated=True)
def get_state_legacy() -> dict[str, str]:
    return get_assistant_state()
