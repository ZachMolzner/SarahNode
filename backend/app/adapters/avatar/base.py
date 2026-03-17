from abc import ABC, abstractmethod
from typing import Any


class AvatarClient(ABC):
    @abstractmethod
    async def initialize(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def dispatch(self, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError
