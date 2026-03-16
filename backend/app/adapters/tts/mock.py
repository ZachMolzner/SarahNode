from app.adapters.tts.base import TTSClient


class MockTTSClient(TTSClient):
    async def synthesize(self, text: str) -> dict:
        duration = max(0.8, len(text) / 45)
        return {"audio_url": "mock://audio", "duration_seconds": duration}
