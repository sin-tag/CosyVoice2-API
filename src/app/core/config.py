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

    # MOSS-TTSD (dialogue/dubbing model, comma-separated devices for multi-GPU)
    moss_enabled: bool = True
    moss_model_path: str = "OpenMOSS-Team/MOSS-TTSD-v1.0"
    moss_device: str = "cuda:0"
    moss_dtype: str = "bfloat16"
    moss_max_speakers: int = 5
    moss_max_new_tokens: int = 2000
    moss_default_temperature: float = 1.1
    moss_default_top_p: float = 0.9
    moss_default_top_k: int = 50
    moss_default_repetition_penalty: float = 1.1

    # Qwen3-TTS (device: comma-separated for multi-GPU, e.g. "cuda:0,cuda:1")
    qwen_enabled: bool = True
    qwen_model_path: str = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    qwen_device: str = "cuda:0"
    qwen_dtype: str = "bfloat16"

    # Audio
    default_sample_rate: int = 24000
    max_text_length: int = 5000
    max_reference_audio_duration_sec: float = 30.0
    min_reference_audio_duration_sec: float = 1.0

    # Performance
    max_concurrent_generations: int = 2
    generation_timeout_sec: int = 120
    max_concurrent_requests: int = 50


settings = Settings()
