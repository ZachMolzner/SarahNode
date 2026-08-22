from __future__ import annotations

import pytest

from app.memory.safe_learning import SafeMemoryLearningService
from app.memory.secret_guard import MemorySecretRejected, detect_persistent_secret
from app.memory.state_manager import MemoryManager
from app.schemas.chat import ChatMessage
from app.schemas.identity import MemoryCategory, MemorySource
from app.services.identity_service import IdentityService
from app.services.safe_identity_service import SafeIdentityService


def _safe_store(tmp_path) -> SafeIdentityService:
    return SafeIdentityService(storage_path=str(tmp_path / "identity.json"))


def test_secret_detector_blocks_credentials_but_not_normal_preferences() -> None:
    assert detect_persistent_secret(value="I prefer dark mode") is None
    assert detect_persistent_secret(value="My goal is to learn API security") is None
    assert detect_persistent_secret(value="I use a password manager") is None
    assert detect_persistent_secret(value="I am learning API key security") is None
    assert detect_persistent_secret(key="spinning_preference", value="I like spinning classes") is None
    assert detect_persistent_secret(key="i_use_a_password_manager", value="I use a password manager") is None
    assert detect_persistent_secret(key="api_key_security", value="I am learning API key security") is None

    assert detect_persistent_secret(value="my password is example-do-not-use-123") is not None
    assert detect_persistent_secret(key="api_key", value="example-value") is not None
    assert detect_persistent_secret(key="openai_api_key", value="example-value") is not None
    assert detect_persistent_secret(key="work_password", value="example-value") is not None
    assert detect_persistent_secret(value="Authorization: Bearer example-token-value") is not None
    assert detect_persistent_secret(value="sk-proj-abcdefghijklmnopqrstuvwxyz123456") is not None
    assert detect_persistent_secret(value="-----BEGIN PRIVATE KEY-----") is not None


def test_safe_identity_service_allows_normal_memory(tmp_path) -> None:
    store = _safe_store(tmp_path)
    item = store.add_memory_item(
        scope="zach",
        category=MemoryCategory.preference,
        source=MemorySource.explicit,
        key="theme_preference",
        value="I prefer dark mode",
        confidence=1.0,
        sensitive=False,
    )
    assert item.value == "I prefer dark mode"
    assert [row.id for row in store.list_memory_items()] == [item.id]


def test_safe_identity_service_rejects_secret_add_and_update(tmp_path) -> None:
    store = _safe_store(tmp_path)

    with pytest.raises(MemorySecretRejected):
        store.add_memory_item(
            scope="zach",
            category=MemoryCategory.knowledge,
            source=MemorySource.explicit,
            key="api_key",
            value="example-value",
            confidence=1.0,
            sensitive=False,
        )

    item = store.add_memory_item(
        scope="zach",
        category=MemoryCategory.preference,
        source=MemorySource.explicit,
        key="editor",
        value="I prefer VS Code",
        confidence=1.0,
        sensitive=False,
    )
    with pytest.raises(MemorySecretRejected):
        store.update_memory_item(item.id, {"value": "my access token is example-token-value"})

    unchanged = store.list_memory_items()[0]
    assert unchanged.value == "I prefer VS Code"


def test_deterministic_explicit_memory_capture_ignores_secret_request(tmp_path) -> None:
    store = _safe_store(tmp_path)
    learning = SafeMemoryLearningService(identity_service=store)

    blocked = learning.classify_explicit_memory_request(
        "Remember that my password is example-do-not-use-123"
    )
    assert blocked is not None
    assert blocked.status == "blocked_secret"

    captured = learning.capture_explicit_memory(
        "Remember that my password is example-do-not-use-123",
        scope="zach",
    )
    assert captured is None
    assert store.list_memory_items() == []


def test_benign_password_manager_memory_is_allowed_and_classified(tmp_path) -> None:
    store = _safe_store(tmp_path)
    learning = SafeMemoryLearningService(identity_service=store)

    decision = learning.classify_explicit_memory_request(
        "Remember that I use a password manager"
    )
    assert decision is not None
    assert decision.status == "safe_memory"

    captured = learning.capture_explicit_memory(
        "Remember that I use a password manager",
        scope="zach",
    )
    assert captured is not None
    assert captured.value == "I use a password manager"
    assert len(store.list_memory_items()) == 1


def test_session_memory_redacts_secret_but_keeps_benign_security_context() -> None:
    memory = MemoryManager(window_size=8)
    memory.add_message(
        ChatMessage(
            user_id="zach",
            username="zach",
            content="Remember that my password is example-do-not-use-123",
        )
    )

    history = "\n".join(memory.recent_history())
    summary = memory.summarize()
    assert "example-do-not-use-123" not in history
    assert "example-do-not-use-123" not in summary
    assert "credential or secret omitted" in history

    memory.add_message(
        ChatMessage(
            user_id="zach",
            username="zach",
            content="Remember that I use a password manager",
        )
    )
    assert "I use a password manager" in "\n".join(memory.recent_history())


def test_legacy_secret_row_is_filtered_from_safe_retrieval(tmp_path) -> None:
    path = tmp_path / "identity.json"
    legacy = IdentityService(storage_path=str(path))
    legacy.add_memory_item(
        scope="zach",
        category=MemoryCategory.knowledge,
        source=MemorySource.explicit,
        key="api_key",
        value="legacy-example-value",
        confidence=1.0,
        sensitive=False,
    )

    hardened = SafeIdentityService(storage_path=str(path))
    assert hardened.list_memory_items() == []
