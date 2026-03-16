from app.schemas.chat import ChatMessage


class ChatIngestionService:
    def mock_message(self, username: str, content: str, priority: int = 1) -> ChatMessage:
        return ChatMessage(user_id=username.lower(), username=username, content=content, priority=priority)
