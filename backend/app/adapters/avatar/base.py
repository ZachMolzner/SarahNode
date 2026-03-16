from abc import ABC, abstractmethod
from typing import Any


class AvatarClient(ABC):
    @abstractmethod
    async def dispatch(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        raise NotImplementedError
