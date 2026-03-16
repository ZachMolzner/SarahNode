from app.schemas.chat import ChatMessage, MessageSource


class ChatIngestionService:
    def mock_message(self, username: str, content: str, priority: int = 1) -> ChatMessage:
        normalized_username = username.strip()
        user_id = normalized_username.lower().replace(" ", "-")

        return ChatMessage(
            user_id=user_id,
            username=normalized_username,
            content=content.strip(),
            source=MessageSource.mock,
            priority=priority,
        )
