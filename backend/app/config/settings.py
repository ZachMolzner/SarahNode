from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings(BaseSettings):
    app_name: str = "SarahNode Personal Assistant"
    env: str = "dev"
    log_level: str = "INFO"

    assistant_cooldown_seconds: float = 1.0
    assistant_max_queue_size: int = 200
    assistant_memory_window: int = 25
    local_data_dir: str = "data"
    identity_store_path: str = "identity_memory.json"

    llm_provider: str = "auto"
    tts_provider: str = "auto"
    stt_provider: str = "auto"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_transcription_model: str = "whisper-1"

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    web_search_provider: str = "none"
    brave_search_api_key: str = ""
    serpapi_api_key: str = ""
    web_search_max_results: int = 5

    web_fetch_max_pages: int = 3
    web_fetch_timeout_seconds: float = 6.0
    web_fetch_max_chars: int = 6000

    backend_bind_all_interfaces: bool = False
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    cors_allowed_origins_raw: str = "http://localhost:5173,http://127.0.0.1:5173,tauri://localhost"
    cors_allow_credentials: bool = False

    allowed_ws_origins_raw: str = "http://localhost:5173,http://127.0.0.1:5173,tauri://localhost"

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


def resolve_backend_host() -> str:
    return "0.0.0.0" if settings.backend_bind_all_interfaces else settings.backend_host


def resolve_cors_origins() -> list[str]:
    origins = _parse_csv(settings.cors_allowed_origins_raw)
    return origins if origins else ["http://localhost:5173", "http://127.0.0.1:5173", "tauri://localhost"]


def resolve_ws_allowed_origins() -> set[str]:
    return set(_parse_csv(settings.allowed_ws_origins_raw))


def resolve_local_data_dir() -> Path:
    candidate = Path(settings.local_data_dir)
    if candidate.is_absolute():
        return candidate
    return Path(__file__).resolve().parents[1] / candidate


def resolve_identity_store_path() -> Path:
    configured = Path(settings.identity_store_path)
    if configured.is_absolute():
        return configured
    return resolve_local_data_dir() / configured
