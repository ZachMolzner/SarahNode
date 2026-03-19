from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.identity import (
    AddressingContext,
    IdentityFact,
    MemoryCategory,
    MemoryItem,
    MemorySource,
    PersonProfile,
    RelationType,
    ResponseStyle,
    SharedProfile,
    SpeakerIdentityResult,
    TonePreference,
    UnknownProfile,
)

HIGH_CONFIDENCE_THRESHOLD = 0.86


class IdentityService:
    def __init__(self, storage_path: str) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load_state()

    def _default_state(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        zach = PersonProfile(
            id="zach",
            display_name="Zach",
            preferred_address="Zach",
            relation=RelationType.self_user,
            tone_preference=TonePreference.playful_flirt,
            response_style=ResponseStyle.concise,
        )
        aleena = PersonProfile(
            id="aleena",
            display_name="Aleena",
            preferred_address="Aleena",
            alternate_addresses=["Mama"],
            relation=RelationType.spouse,
            tone_preference=TonePreference.warm,
            response_style=ResponseStyle.balanced,
        )
        shared = SharedProfile(id="household", members=["zach", "aleena"])
        facts = [
            {
                "id": "fact-primary-user",
                "scope": "zach",
                "category": "identity",
                "source": "explicit",
                "key": "primary_user",
                "value": "Zach is the primary user",
                "confidence": 1.0,
                "immutable_by_inference": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "fact-spouse",
                "scope": "household",
                "category": "identity",
                "source": "explicit",
                "key": "family_relation",
                "value": "Aleena is Zach's wife",
                "confidence": 1.0,
                "immutable_by_inference": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "fact-zach-address",
                "scope": "zach",
                "category": "identity",
                "source": "explicit",
                "key": "preferred_address",
                "value": "Address Zach as Zach",
                "confidence": 1.0,
                "immutable_by_inference": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "fact-aleena-address",
                "scope": "aleena",
                "category": "identity",
                "source": "explicit",
                "key": "preferred_address",
                "value": "Address Aleena as Aleena",
                "confidence": 1.0,
                "immutable_by_inference": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "fact-aleena-mama",
                "scope": "aleena",
                "category": "identity",
                "source": "explicit",
                "key": "alternate_address",
                "value": "Aleena may occasionally be addressed as Mama",
                "confidence": 1.0,
                "immutable_by_inference": True,
                "created_at": now,
                "updated_at": now,
            },
        ]

        return {
            "profiles": {
                "zach": zach.model_dump(mode="json"),
                "aleena": aleena.model_dump(mode="json"),
            },
            "shared_profiles": {"household": shared.model_dump(mode="json")},
            "unknown_profile": UnknownProfile().model_dump(mode="json"),
            "explicit_identity_facts": facts,
            "memory_items": [],
            "speaker": {
                "high_confidence_threshold": HIGH_CONFIDENCE_THRESHOLD,
                "unknown_fallback": "unknown",
            },
            "nickname_policy": {
                "aleena_mama_enabled": True,
                "aleena_mama_usage_ratio": 0.28,
            },
            "version": 1,
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.storage_path.exists():
            state = self._default_state()
            self._save_state(state)
            return state

        parsed = json.loads(self.storage_path.read_text(encoding="utf-8"))
        defaults = self._default_state()
        merged = {**defaults, **parsed}
        merged["profiles"] = {**defaults["profiles"], **parsed.get("profiles", {})}
        merged["shared_profiles"] = {**defaults["shared_profiles"], **parsed.get("shared_profiles", {})}
        return merged

    def _save_state(self, state: dict[str, Any] | None = None) -> None:
        payload = state or self._state
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def snapshot(self) -> dict[str, Any]:
        return self._state

    def list_profiles(self) -> dict[str, Any]:
        return {
            "profiles": list(self._state["profiles"].values()),
            "shared_profiles": list(self._state["shared_profiles"].values()),
            "unknown_profile": self._state["unknown_profile"],
        }

    def list_identity_facts(self) -> list[IdentityFact]:
        return [IdentityFact.model_validate(item) for item in self._state["explicit_identity_facts"]]

    def list_memory_items(self, scope: str | None = None) -> list[MemoryItem]:
        items = [MemoryItem.model_validate(item) for item in self._state["memory_items"]]
        if scope:
            return [item for item in items if item.scope == scope]
        return items

    def update_profile(self, profile_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        profiles = self._state["profiles"]
        if profile_id not in profiles:
            raise KeyError(profile_id)

        current = profiles[profile_id]
        next_profile = {**current, **patch}
        # explicit identity facts are authoritative over inferred updates
        facts_by_key = {fact["key"]: fact for fact in self._state["explicit_identity_facts"] if fact["scope"] == profile_id}
        if "preferred_address" in facts_by_key and patch.get("inferred_update"):
            next_profile["preferred_address"] = current["preferred_address"]

        cleaned = PersonProfile.model_validate(next_profile)
        profiles[profile_id] = cleaned.model_dump(mode="json")
        self._save_state()
        return profiles[profile_id]

    def set_nickname_policy(self, enabled: bool, usage_ratio: float | None = None) -> dict[str, Any]:
        ratio = self._state["nickname_policy"].get("aleena_mama_usage_ratio", 0.28)
        if usage_ratio is not None:
            ratio = max(0.0, min(1.0, usage_ratio))
        self._state["nickname_policy"] = {
            "aleena_mama_enabled": bool(enabled),
            "aleena_mama_usage_ratio": ratio,
        }
        self._save_state()
        return self._state["nickname_policy"]

    def set_voice_profile_id(self, profile_id: str, voice_profile_id: str | None) -> dict[str, Any]:
        if profile_id not in self._state["profiles"]:
            raise KeyError(profile_id)

        person = PersonProfile.model_validate(self._state["profiles"][profile_id])
        updated = person.model_copy(update={"voice_profile_id": voice_profile_id})
        self._state["profiles"][profile_id] = updated.model_dump(mode="json")
        self._save_state()
        return self._state["profiles"][profile_id]

    def reset_voice_profile(self, profile_id: str) -> dict[str, Any]:
        return self.set_voice_profile_id(profile_id, None)

    def add_memory_item(
        self,
        scope: str,
        category: MemoryCategory,
        source: MemorySource,
        key: str,
        value: str,
        confidence: float,
        sensitive: bool,
    ) -> MemoryItem:
        # Guardrail: never infer identity overrides.
        if source == MemorySource.inferred and category == MemoryCategory.identity:
            raise ValueError("Inferred identity memory is blocked. Use explicit identity editing.")

        item = MemoryItem(
            id=f"mem-{uuid4().hex[:10]}",
            scope=scope,
            category=category,
            source=source,
            key=key,
            value=value,
            confidence=confidence,
            sensitive=sensitive,
        )
        self._state["memory_items"].append(item.model_dump(mode="json"))
        self._save_state()
        return item

    def update_memory_item(self, item_id: str, patch: dict[str, Any]) -> MemoryItem:
        now = datetime.now(timezone.utc).isoformat()
        for idx, raw in enumerate(self._state["memory_items"]):
            if raw["id"] != item_id:
                continue
            merged = {**raw, **patch, "updated_at": now}
            item = MemoryItem.model_validate(merged)
            self._state["memory_items"][idx] = item.model_dump(mode="json")
            self._save_state()
            return item
        raise KeyError(item_id)

    def delete_memory_item(self, item_id: str) -> None:
        existing = self._state["memory_items"]
        next_items = [item for item in existing if item.get("id") != item_id]
        if len(next_items) == len(existing):
            raise KeyError(item_id)
        self._state["memory_items"] = next_items
        self._save_state()

    def resolve_speaker(
        self,
        username: str | None = None,
        voice_profile_id: str | None = None,
        confidence: float | None = None,
    ) -> SpeakerIdentityResult:
        if username:
            normalized = username.strip().lower()
            if normalized in self._state["profiles"]:
                return SpeakerIdentityResult(
                    speaker_id=normalized,
                    confidence=1.0,
                    is_high_confidence=True,
                    source="explicit",
                )

        if voice_profile_id:
            for profile_id, profile in self._state["profiles"].items():
                if profile.get("voice_profile_id") == voice_profile_id:
                    score = confidence if confidence is not None else 0.0
                    high = score >= self._state["speaker"].get("high_confidence_threshold", HIGH_CONFIDENCE_THRESHOLD)
                    return SpeakerIdentityResult(
                        speaker_id=profile_id if high else "unknown",
                        confidence=score,
                        is_high_confidence=high,
                        source="voice_match" if high else "fallback",
                    )

        return SpeakerIdentityResult(speaker_id="unknown", confidence=confidence or 0.0, is_high_confidence=False, source="fallback")

    def addressing_context(
        self,
        speaker: SpeakerIdentityResult,
        conversation_mode: str | None = None,
        turn_index: int | None = None,
    ) -> AddressingContext:
        if conversation_mode == "shared":
            return AddressingContext(
                mode="shared",
                address_name="Zach and Aleena",
                tone_directive="Use warm collaborative language; avoid flirtatious phrasing in shared mode.",
                deterministic_rule="Shared context uses household addressing",
            )

        if speaker.speaker_id == "zach":
            profile = PersonProfile.model_validate(self._state["profiles"]["zach"])
            return AddressingContext(
                mode="personal",
                address_name=profile.preferred_address,
                tone_hint=profile.tone_preference,
                tone_directive=(
                    "Zach-only tone: be playful and lightly flirtatious while remaining respectful, useful, and controlled. "
                    "Keep technical guidance precise and concise."
                ),
                response_style_hint=profile.response_style,
                deterministic_rule="Identified Zach: use direct concise defaults",
            )

        if speaker.speaker_id == "aleena" and speaker.is_high_confidence:
            profile = PersonProfile.model_validate(self._state["profiles"]["aleena"])
            use_mama = False
            if profile.alternate_addresses and self._state["nickname_policy"].get("aleena_mama_enabled", True):
                ratio = float(self._state["nickname_policy"].get("aleena_mama_usage_ratio", 0.28))
                turn_value = turn_index if turn_index is not None else random.randint(1, 100)
                use_mama = (turn_value % 100) < int(ratio * 100)

            name = profile.alternate_addresses[0] if use_mama else profile.preferred_address
            return AddressingContext(
                mode="personal",
                address_name=name,
                allow_alternate=bool(profile.alternate_addresses),
                alternate_candidates=profile.alternate_addresses,
                tone_hint=profile.tone_preference,
                tone_directive="Use warm and supportive tone for Aleena. Avoid flirtatious language.",
                response_style_hint=profile.response_style,
                deterministic_rule="Identified Aleena: default Aleena, occasional Mama",
            )

        return AddressingContext(
            mode="unknown",
            address_name="there",
            tone_hint=TonePreference.neutral,
            tone_directive="Unknown speaker: keep tone neutral, polite, and practical.",
            response_style_hint=ResponseStyle.balanced,
            deterministic_rule="Unknown speaker fallback",
        )
