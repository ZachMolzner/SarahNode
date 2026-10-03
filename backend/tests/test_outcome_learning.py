from pathlib import Path

from app.memory.safe_learning import SafeMemoryLearningService
from app.services.safe_identity_service import SafeIdentityService


def build_service(tmp_path: Path) -> SafeMemoryLearningService:
    identity = SafeIdentityService(storage_path=str(tmp_path / "identity.json"))
    return SafeMemoryLearningService(identity_service=identity)


def test_success_feedback_learns_prior_fix(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    item = service.capture_outcome_feedback(
        "That fixed it!",
        previous_user_text="My Zebra printer is connected by USB but will not print.",
        previous_reply="Check whether Windows created the correct Zebra printer queue and verify the driver.",
        scope="zach",
    )

    assert item is not None
    assert item.category.value == "experience"
    assert item.source.value == "inferred"
    assert "Zebra printer" in item.value
    assert "confirmed" in item.value


def test_explicit_actual_fix_replaces_prior_answer(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    item = service.capture_outcome_feedback(
        "The actual fix was changing the printer driver to ZDesigner.",
        previous_user_text="My Zebra printer printed garbled text.",
        previous_reply="Try reinstalling the printer.",
        scope="zach",
    )

    assert item is not None
    assert "ZDesigner" in item.value
    assert "Try reinstalling" not in item.value


def test_generic_thanks_does_not_create_learning(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    item = service.capture_outcome_feedback(
        "Thanks!",
        previous_user_text="My laptop cannot connect.",
        previous_reply="Check the adapter status.",
        scope="zach",
    )
    assert item is None


def test_feedback_learning_refuses_secret_shaped_content(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    item = service.capture_outcome_feedback(
        "That worked!",
        previous_user_text="My password is example-do-not-use-123 and login fails.",
        previous_reply="Reset the password.",
        scope="zach",
    )
    assert item is None
