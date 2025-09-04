"""Voice models for CosyVoice2 API"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

class VoiceType(str, Enum):
    SFT = "sft"
    ZERO_SHOT = "zero_shot"
    CROSS_LINGUAL = "cross_lingual"
    INSTRUCT = "instruct"

class AudioFormat(str, Enum):
    WAV = "wav"
    MP3 = "mp3"
    FLAC = "flac"

class VoiceBase(BaseModel):
    voice_id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Human-readable voice name")
    description: Optional[str] = Field(None, description="Voice description")
    voice_type: VoiceType = Field(..., description="Type of voice")
    language: Optional[str] = Field(None, description="Primary language of the voice (supports multilingual)")

class VoiceCreate(VoiceBase):
    prompt_text: Optional[str] = Field(None, description="Text that matches the audio sample")
    audio_format: AudioFormat = Field(AudioFormat.WAV, description="Audio file format")

class VoiceUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Human-readable voice name")
    description: Optional[str] = Field(None, description="Voice description")
    language: Optional[str] = Field(None, description="Primary language of the voice")

class VoiceInDB(VoiceBase):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    audio_file_path: Optional[str] = Field(None, description="Path to audio file")
    prompt_text: Optional[str] = Field(None, description="Text that matches the audio sample")
    audio_format: AudioFormat = Field(AudioFormat.WAV, description="Audio file format")
    file_size: Optional[int] = Field(None, description="Audio file size in bytes")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    sample_rate: Optional[int] = Field(None, description="Audio sample rate")
    model_data: Optional[Dict[str, Any]] = Field(None, description="Model-specific data for voice synthesis")
    is_active: bool = Field(True, description="Whether the voice is active")

class VoiceResponse(VoiceBase):
    created_at: datetime
    updated_at: datetime
    audio_format: AudioFormat
    file_size: Optional[int] = None
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    is_active: bool = True

class VoiceListResponse(BaseModel):
    voices: List[VoiceResponse]
    total: int
    page: int = 1
    per_page: int = 10

class VoiceStats(BaseModel):
    total_voices: int = 0
    active_voices: int = 0
    voice_types: dict = Field(default_factory=dict)
    languages: dict = Field(default_factory=dict)
    total_duration: float = 0.0
    total_size: int = 0
