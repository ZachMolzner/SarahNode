import asyncio
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config.settings import settings

from .base import STTClient


class OpenAITranscriptionClient(STTClient):
    provider_name = "openai"

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI transcription.")

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_transcription_model

    async def transcribe(self, file_path: Path, mime_type: str | None = None) -> dict[str, Any]:
        def _run() -> Any:
            with file_path.open("rb") as audio_file:
                return self._client.audio.transcriptions.create(
                    model=self._model,
                    file=audio_file,
                )

        result = await asyncio.to_thread(_run)
        text = getattr(result, "text", "")

        return {
            "text": text,
            "provider": {
                "name": self.provider_name,
                "model": self._model,
                "mime_type": mime_type,
            },
        }
