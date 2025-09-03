"""
Configuration settings for CosyVoice2 API
"""

import os
from typing import List, Optional

try:
    # Pydantic v2 - try pydantic-settings first
    from pydantic_settings import BaseSettings
    from pydantic import Field
    PYDANTIC_SETTINGS_AVAILABLE = True
except ImportError:
    try:
        # Install pydantic-settings automatically
        import subprocess
        import sys
        print("Installing pydantic-settings...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pydantic-settings>=2.0.0"])
        from pydantic_settings import BaseSettings
        from pydantic import Field
        PYDANTIC_SETTINGS_AVAILABLE = True
        print("✓ pydantic-settings installed successfully")
    except Exception:
        # Last resort - try pydantic v1 style (will likely fail with v2)
        try:
            from pydantic import BaseSettings, Field
            PYDANTIC_SETTINGS_AVAILABLE = False
            print("⚠️  Using legacy BaseSettings - may not work with Pydantic v2")
        except ImportError:
            raise ImportError(
                "Cannot import BaseSettings. Please install pydantic-settings: "
                "pip install pydantic-settings>=2.0.0"
            )


class Settings(BaseSettings):
    """Application settings"""
    
    # Server settings
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = Field(
        default=["*"], 
        env="ALLOWED_ORIGINS"
    )
    
    # Model settings
    MODEL_DIR: str = Field(
        default="models/CosyVoice2-0.5B",
        env="MODEL_DIR",
        description="Path to CosyVoice model directory"
    )
    
    # Voice cache settings
    VOICE_CACHE_DIR: str = Field(
        default="voice_cache",
        env="VOICE_CACHE_DIR",
        description="Directory to store cached voices"
    )
    
    VOICE_CACHE_DB: str = Field(
        default="voice_cache/voices.json",
        env="VOICE_CACHE_DB",
        description="Path to voice cache database file"
    )
    
    # Audio settings
    SUPPORTED_AUDIO_FORMATS: List[str] = Field(
        default=["wav", "mp3", "flac", "m4a"],
        description="Supported audio file formats"
    )
    
    MAX_AUDIO_DURATION: int = Field(
        default=30,
        env="MAX_AUDIO_DURATION",
        description="Maximum audio duration in seconds for voice cloning"
    )
    
    SAMPLE_RATE: int = Field(
        default=22050,
        env="SAMPLE_RATE",
        description="Audio sample rate"
    )
    
    # Processing settings
    MAX_TEXT_LENGTH: int = Field(
        default=1000,
        env="MAX_TEXT_LENGTH",
        description="Maximum text length for synthesis"
    )
    
    DEFAULT_SPEED: float = Field(
        default=1.0,
        env="DEFAULT_SPEED",
        description="Default synthesis speed"
    )
    
    # File upload settings
    MAX_FILE_SIZE: int = Field(
        default=50 * 1024 * 1024,  # 50MB
        env="MAX_FILE_SIZE",
        description="Maximum file upload size in bytes"
    )
    
    # Output settings
    OUTPUT_DIR: str = Field(
        default="outputs",
        env="OUTPUT_DIR",
        description="Directory for generated audio files"
    )
    
    # Cleanup settings
    CLEANUP_INTERVAL: int = Field(
        default=3600,  # 1 hour
        env="CLEANUP_INTERVAL",
        description="Interval for cleaning up temporary files (seconds)"
    )
    
    TEMP_FILE_LIFETIME: int = Field(
        default=7200,  # 2 hours
        env="TEMP_FILE_LIFETIME",
        description="Lifetime of temporary files (seconds)"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()

# Ensure required directories exist
os.makedirs(settings.VOICE_CACHE_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(settings.VOICE_CACHE_DB), exist_ok=True)
