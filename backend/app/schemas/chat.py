from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class MessageSource(str, Enum):
    mock = "mock"
    stream = "stream"


class ChatMessage(BaseModel):
    user_id: str
    username: str
    content: str = Field(min_length=1, max_length=500)
    source: MessageSource = MessageSource.mock
    priority: int = Field(default=1, ge=0, le=10)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModerationResult(BaseModel):
    allowed: bool
    reason: str | None = None
    category: str | None = None


class AssistantReply(BaseModel):
    text: str
    emotion: str = "idle"
    should_speak: bool = True
