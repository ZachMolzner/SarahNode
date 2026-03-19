from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class RelationType(str, Enum):
    self_user = "self"
    spouse = "spouse"
    guest = "guest"


class TonePreference(str, Enum):
    playful_flirt = "playful_flirt"
    direct = "direct"
    warm = "warm"
    neutral = "neutral"


class ResponseStyle(str, Enum):
    concise = "concise"
    balanced = "balanced"
    detailed = "detailed"


class ProfileType(str, Enum):
    person = "person"
    shared = "shared"
    fallback = "fallback"


class PersonProfile(BaseModel):
    id: str
    type: Literal[ProfileType.person] = ProfileType.person
    display_name: str
    preferred_address: str
    alternate_addresses: list[str] = Field(default_factory=list)
    relation: RelationType = RelationType.guest
    tone_preference: TonePreference = TonePreference.neutral
    response_style: ResponseStyle = ResponseStyle.balanced
    voice_profile_id: str | None = None


class SharedProfile(BaseModel):
    id: str
    type: Literal[ProfileType.shared] = ProfileType.shared
    members: list[str] = Field(default_factory=list)


class UnknownProfile(BaseModel):
    id: str = "unknown"
    type: Literal[ProfileType.fallback] = ProfileType.fallback
    display_name: str = "Guest"
    preferred_address: str = "there"


class IdentityFact(BaseModel):
    id: str
    scope: str
    category: Literal["identity"] = "identity"
    source: Literal["explicit"] = "explicit"
    key: str
    value: str
    confidence: float = 1.0
    immutable_by_inference: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryCategory(str, Enum):
    identity = "identity"
    preference = "preference"
    habit = "habit"
    routine = "routine"


class MemorySource(str, Enum):
    explicit = "explicit"
    inferred = "inferred"


class MemoryItem(BaseModel):
    id: str
    scope: str = Field(description="zach, aleena, or household")
    category: MemoryCategory
    source: MemorySource
    key: str
    value: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    sensitive: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SpeakerIdentityResult(BaseModel):
    speaker_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    is_high_confidence: bool
    source: Literal["explicit", "voice_match", "fallback"]


class AddressingContext(BaseModel):
    mode: Literal["personal", "shared", "unknown"]
    address_name: str
    allow_alternate: bool = False
    alternate_candidates: list[str] = Field(default_factory=list)
    tone_hint: TonePreference = TonePreference.neutral
    tone_directive: str = "Stay neutral and helpful."
    response_style_hint: ResponseStyle = ResponseStyle.balanced
    deterministic_rule: str
