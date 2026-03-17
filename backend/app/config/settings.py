from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SarahNode Personal Assistant"
    env: str = "dev"
    log_level: str = "INFO"

    assistant_cooldown_seconds: float = 1.0
    assistant_max_queue_size: int = 200
    assistant_memory_window: int = 25

    llm_provider: str = "auto"
    tts_provider: str = "auto"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    public_api_base_url: str = "http://localhost:8000"
    public_ws_base_url: str = "ws://localhost:8000"

    persona_name: str = "Sarah"
    persona_style: str = "clear, warm, and practical"
    persona_system_prompt: str = Field(
        default=(
            "You are Sarah, a local-first personal AI companion. "
            "Be concise, helpful, safe, and action-oriented."
        )
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
