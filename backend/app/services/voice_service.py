import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.adapters.stt.base import STTClient

logger = logging.getLogger(__name__)


class VoiceService:
    def __init__(self, stt_client: STTClient | None) -> None:
        self.stt_client = stt_client

    async def transcribe_upload(self, upload: UploadFile) -> dict[str, Any]:
        if self.stt_client is None:
            raise RuntimeError("Speech-to-text provider is not configured.")

        suffix = Path(upload.filename or "recording.webm").suffix or ".webm"
        start = time.perf_counter()

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            data = await upload.read()
            temp_path.write_bytes(data)
            transcript = await self.stt_client.transcribe(temp_path, upload.content_type)
            duration_ms = int((time.perf_counter() - start) * 1000)

            return {
                "text": transcript.get("text", ""),
                "provider": transcript.get("provider", {}),
                "duration_ms": duration_ms,
            }
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to delete temp audio file: %s", temp_path)
