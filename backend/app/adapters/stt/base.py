from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class STTClient(ABC):
    provider_name: str = "unknown"

    @abstractmethod
    async def transcribe(self, file_path: Path, mime_type: str | None = None) -> dict[str, Any]:
        """Transcribe an audio file and return structured metadata."""
