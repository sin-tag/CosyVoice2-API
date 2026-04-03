from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env relative to project root (parent of src/)
_env_file = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = {"env_file": str(_env_file), "env_file_encoding": "utf-8", "extra": "ignore"}

    # App
    environment: str = "production"
    debug: bool = False
    app_name: str = "voice-fast-service"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./storage/voice_fast.db"

    # Auth
    api_key: str = "change-me-in-production"

    # IP Whitelist — comma-separated list of allowed IPs (empty = allow all)
    allowed_ips: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Storage
    voices_storage_path: str = "./storage/voices"
    history_storage_path: str = "./storage/history"

    # OmniVoice (600+ languages, voice cloning + voice design)
    omni_enabled: bool = True
    omni_model_path: str = "k2-fsa/OmniVoice"
    omni_device: str = "cuda:0"
    omni_dtype: str = "float16"

    # Audio
    default_sample_rate: int = 24000
    max_text_length: int = 5000
    max_reference_audio_duration_sec: float = 30.0
    min_reference_audio_duration_sec: float = 1.0

    # Performance
    max_concurrent_generations: int = 2
    generation_timeout_sec: int = 120
    max_concurrent_requests: int = 50
    max_queue_size: int = 100


settings = Settings()
