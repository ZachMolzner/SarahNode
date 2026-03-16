from typing import Any

from app.adapters.tts.base import TTSClient


class MockTTSClient(TTSClient):
    async def synthesize(self, text: str) -> dict[str, Any]:
        duration = max(0.8, len(text) / 45)
        return {
            "provider": "mock_tts",
            "audio_url": "mock://audio",
            "duration_seconds": round(duration, 2),
            "text_preview": text[:80],
        }
