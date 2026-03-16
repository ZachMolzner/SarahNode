from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SarahNode"
    env: str = "dev"
    log_level: str = "INFO"
    assistant_cooldown_seconds: float = 1.5
    assistant_max_queue_size: int = 200
    assistant_memory_window: int = 25

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
