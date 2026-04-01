import logging

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.container import (
    assistant_intake_service,
    identity_service,
    memory_manager,
    provider_status,
    stream_orchestrator,
    voice_service,
)
from app.schemas.identity import MemoryCategory, MemorySource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["assistant"])


class AssistantMessageRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=500)
    priority: int = Field(default=1, ge=0, le=10)
    conversation_mode: str = Field(default="personal", pattern="^(personal|shared)$")


@router.post("/assistant/messages")
async def send_assistant_message(request: AssistantMessageRequest) -> dict[str, str]:
    message = assistant_intake_service.build_message(
        username=request.username,
        content=request.content,
        priority=request.priority,
        conversation_mode=request.conversation_mode,
    )
    await stream_orchestrator.enqueue_message(message)
    return {"status": "queued"}


class ProfilePatchRequest(BaseModel):
    preferred_address: str | None = Field(default=None, min_length=1, max_length=48)
    alternate_addresses: list[str] | None = None
    tone_preference: str | None = None
    response_style: str | None = None


class NicknamePolicyRequest(BaseModel):
    enabled: bool
    usage_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class VoiceEnrollmentRequest(BaseModel):
    voice_profile_id: str = Field(min_length=1, max_length=128)


class VoiceMatchRequest(BaseModel):
    voice_profile_id: str | None = Field(default=None, max_length=128)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    username_hint: str | None = Field(default=None, max_length=64)
    shared_context: bool = False


class MemoryItemCreateRequest(BaseModel):
    scope: str = Field(pattern="^(zach|aleena|household)$")
    category: MemoryCategory
    source: MemorySource
    key: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=500)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    sensitive: bool = False


class MemoryItemPatchRequest(BaseModel):
    value: str | None = Field(default=None, min_length=1, max_length=500)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    sensitive: bool | None = None




class VoiceEventRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)


@router.post("/assistant/voice/event")
async def emit_voice_event(request: VoiceEventRequest) -> dict[str, str]:
    if not request.event_type.startswith("voice:"):
        raise HTTPException(status_code=400, detail="event_type must start with 'voice:'")

    await stream_orchestrator.emit_event(request.event_type, {})
    return {"status": "ok"}


@router.get("/assistant/identity")
def get_identity_state() -> dict[str, object]:
    state = identity_service.snapshot()
    return {
        "profiles": list(state["profiles"].values()),
        "shared_profiles": list(state["shared_profiles"].values()),
        "unknown_profile": state["unknown_profile"],
        "explicit_identity_facts": state["explicit_identity_facts"],
        "nickname_policy": state["nickname_policy"],
        "speaker": state["speaker"],
    }


@router.patch("/assistant/identity/profiles/{profile_id}")
def patch_profile(profile_id: str, request: ProfilePatchRequest) -> dict[str, object]:
    try:
        payload = request.model_dump(exclude_none=True)
        return {"profile": identity_service.update_profile(profile_id, payload)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from exc


@router.patch("/assistant/identity/nickname-policy")
def patch_nickname_policy(request: NicknamePolicyRequest) -> dict[str, object]:
    return {"nickname_policy": identity_service.set_nickname_policy(request.enabled, request.usage_ratio)}


@router.post("/assistant/voice/enroll/{profile_id}")
def enroll_voice_profile(profile_id: str, request: VoiceEnrollmentRequest) -> dict[str, object]:
    try:
        profile = identity_service.set_voice_profile_id(profile_id, request.voice_profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from exc
    return {"profile": profile}


@router.post("/assistant/voice/reset/{profile_id}")
def reset_voice_profile(profile_id: str) -> dict[str, object]:
    try:
        profile = identity_service.reset_voice_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}") from exc
    return {"profile": profile}


@router.post("/assistant/voice/match")
def match_voice_profile(request: VoiceMatchRequest) -> dict[str, object]:
    speaker = identity_service.resolve_speaker(
        username=request.username_hint,
        voice_profile_id=request.voice_profile_id,
        confidence=request.confidence,
    )
    addressing = identity_service.addressing_context(
        speaker,
        conversation_mode="shared" if request.shared_context else "personal",
    )
    return {"speaker": speaker.model_dump(mode="json"), "addressing": addressing.model_dump(mode="json")}


@router.get("/assistant/memory")
def list_memory(scope: str | None = None) -> dict[str, object]:
    items = [item.model_dump(mode="json") for item in identity_service.list_memory_items(scope=scope)]
    return {"items": items}


@router.post("/assistant/memory")
def create_memory_item(request: MemoryItemCreateRequest) -> dict[str, object]:
    try:
        item = identity_service.add_memory_item(
            scope=request.scope,
            category=request.category,
            source=request.source,
            key=request.key,
            value=request.value,
            confidence=request.confidence,
            sensitive=request.sensitive,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item.model_dump(mode="json")}


@router.patch("/assistant/memory/{item_id}")
def patch_memory_item(item_id: str, request: MemoryItemPatchRequest) -> dict[str, object]:
    try:
        item = identity_service.update_memory_item(item_id, request.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Memory item not found: {item_id}") from exc
    return {"item": item.model_dump(mode="json")}


@router.delete("/assistant/memory/{item_id}")
def delete_memory_item(item_id: str) -> dict[str, str]:
    try:
        identity_service.delete_memory_item(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Memory item not found: {item_id}") from exc
    return {"status": "deleted"}


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
        await stream_orchestrator.emit_event("voice:error", {"stage": "configuration", "details": "service unavailable"})
        raise HTTPException(status_code=503, detail="Speech-to-text is not configured.") from exc
    except Exception as exc:
        logger.exception("Transcription failed")
        await stream_orchestrator.emit_event("voice:error", {"stage": "transcription", "details": "transcription failed"})
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
    providers = provider_status()
    web_provider = providers.get("web_search", {})
    return {
        "assistant_state": memory_manager.state.assistant_state,
        "latest_reply": memory_manager.state.last_reply,
        "latest_capability_intent": memory_manager.state.last_capability_intent,
        "last_used_live_web": memory_manager.state.last_used_live_web,
        "latest_web_sources": memory_manager.state.latest_web_sources,
        "web_browsing": {
            "enabled": web_provider.get("mode") == "real",
            "provider": web_provider.get("active", "none"),
            "reason": web_provider.get("reason", "Not initialized"),
        },
        "capabilities": [
            "ask_general",
            "lookup_information",
            "browse_web",
            "coding_help",
            "shutdown_command",
            "smalltalk_or_greeting",
        ],
        "memory_summary": memory_manager.summarize(),
        "identity_resolution": {
            "speaker_id": memory_manager.state.last_speaker_id,
            "confidence": memory_manager.state.last_speaker_confidence,
            "address_name": memory_manager.state.last_address_name,
            "mode": memory_manager.state.last_address_mode,
        },
        "providers": provider_status(),
    }


@router.get("/state", deprecated=True)
def get_state_legacy() -> dict[str, str]:
    return get_assistant_state()
