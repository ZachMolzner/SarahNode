from abc import ABC, abstractmethod
from typing import Any


class TTSClient(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> dict[str, Any]:
        raise NotImplementedError
