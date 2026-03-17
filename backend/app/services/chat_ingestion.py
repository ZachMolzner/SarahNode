from app.schemas.chat import ChatMessage, MessageSource


class AssistantIntakeService:
    def build_message(self, username: str, content: str, priority: int = 1) -> ChatMessage:
        normalized_username = username.strip()
        normalized_content = content.strip()

        return ChatMessage(
            user_id=normalized_username.lower().replace(" ", "-") or "local-user",
            username=normalized_username or "Local User",
            content=normalized_content,
            source=MessageSource.web_ui,
            priority=priority,
        )
