from abc import ABC, abstractmethod


class AvatarClient(ABC):
    @abstractmethod
    async def dispatch(self, event_type: str, payload: dict | None = None) -> None:
        raise NotImplementedError
