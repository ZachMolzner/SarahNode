from app.adapters.tts.base import TTSClient


class MockTTSClient(TTSClient):
    async def synthesize(self, text: str) -> dict[str, str | float]:
        return {
            "provider": "mock_tts",
            "mime_type": "audio/mpeg",
            "audio_base64": "",
            "duration_seconds": 0.0,
            "source_text": text,
            "text_preview": text[:120],
            "warning": "TTS API key not configured.",
        }
