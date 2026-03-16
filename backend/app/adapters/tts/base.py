from abc import ABC, abstractmethod


class TTSClient(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> dict:
        raise NotImplementedError
