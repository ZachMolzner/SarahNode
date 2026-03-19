import base64

import httpx

from app.adapters.tts.base import TTSClient
from app.config.settings import settings


class ElevenLabsClient(TTSClient):
    def __init__(
        self,
        api_key: str | None = None,
        voice_id: str | None = None,
        model_id: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.elevenlabs_api_key
        self.voice_id = voice_id or settings.elevenlabs_voice_id
        self.model_id = model_id or settings.elevenlabs_model_id

        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY must be set.")
        if not self.voice_id:
            raise ValueError("ELEVENLABS_VOICE_ID must be set.")

    async def synthesize(self, text: str) -> dict[str, str | float]:
        endpoint = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "accept": "audio/mpeg",
            "content-type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.46,
                "similarity_boost": 0.76,
                "style": 0.18,
                "use_speaker_boost": False,
            },
        }

        async with httpx.AsyncClient(timeout=40.0) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()

        audio_bytes = response.content
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        approx_duration = max(0.6, len(text.split()) * 0.42)

        return {
            "provider": "elevenlabs",
            "model": self.model_id,
            "voice_id": self.voice_id,
            "mime_type": "audio/mpeg",
            "audio_base64": audio_base64,
            "duration_seconds": round(approx_duration, 2),
            "source_text": text,
            "text_preview": text[:120],
        }
