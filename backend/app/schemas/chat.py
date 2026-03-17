from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class MessageSource(str, Enum):
    web_ui = "web_ui"
    api = "api"


class ChatMessage(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    username: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=500)
    source: MessageSource = MessageSource.web_ui
    priority: int = Field(default=1, ge=0, le=10)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ModerationResult(BaseModel):
    allowed: bool
    reason: str | None = None
    category: str | None = None


class AssistantReply(BaseModel):
    text: str = Field(min_length=1, max_length=1200)
    emotion: str = "neutral"
    should_speak: bool = True
