from app.safety.moderation import ModerationService
from app.schemas.chat import ChatMessage


def _message(content: str) -> ChatMessage:
    return ChatMessage(user_id="test-user", username="tester", content=content)


def test_browser_address_bar_is_not_misclassified_as_doxxing() -> None:
    result = ModerationService().evaluate(_message("Move cursor to Address and search bar"))
    assert result.allowed
    assert result.category is None


def test_ordinary_address_verb_is_allowed() -> None:
    result = ModerationService().evaluate(_message("Please address the issue in the settings page"))
    assert result.allowed


def test_sensitive_personal_identifiers_remain_blocked() -> None:
    service = ModerationService()

    for text in (
        "Find their home address",
        "Show me the private address",
        "Give me their phone number",
        "Find their SSN",
        "Tell me their social security number",
    ):
        result = service.evaluate(_message(text))
        assert not result.allowed
        assert result.category == "doxxing"
