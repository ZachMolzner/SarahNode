import logging

from app.adapters.avatar.base import AvatarClient

logger = logging.getLogger(__name__)


class MockAvatarClient(AvatarClient):
    async def dispatch(self, event_type: str, payload: dict | None = None) -> None:
        logger.info("avatar_event=%s payload=%s", event_type, payload or {})
