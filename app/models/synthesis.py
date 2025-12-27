"""Synthesis models for Chatterbox TTS API"""
from typing import Optional
from pydantic import BaseModel, Field
from .voice import AudioFormat

# Cross-lingual with audio file (Chatterbox doesn't require prompt_text)
class CrossLingualWithAudioRequest(BaseModel):
    """Cross-lingual voice cloning with audio file"""
    text: str = Field(..., description="Text to synthesize", max_length=2000)
    prompt_audio_url: str = Field(..., description="URL or path to reference audio file")
    prompt_text: Optional[str] = Field(None, description="Optional reference text (not required for Chatterbox)")
    format: AudioFormat = Field(AudioFormat.WAV, description="Output audio format")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speed multiplier")
    stream: bool = Field(False, description="Enable streaming (default: False)")

# Cross-lingual with cached voice
class CrossLingualWithCacheRequest(BaseModel):
    """Cross-lingual voice cloning with cached voice"""
    text: str = Field(..., description="Text to synthesize", max_length=2000)
    voice_id: str = Field(..., description="Voice ID from cache")
    format: AudioFormat = Field(AudioFormat.WAV, description="Output audio format")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speed multiplier")
    stream: bool = Field(False, description="Enable streaming (default: False)")

class SynthesisResponse(BaseModel):
    """Synthesis response"""
    success: bool = Field(..., description="Whether synthesis was successful")
    message: str = Field(..., description="Response message")
    audio_url: Optional[str] = Field(None, description="URL to download the generated audio")
    file_path: Optional[str] = Field(None, description="Local file path to generated audio")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    format: AudioFormat = Field(..., description="Audio format")
    synthesis_time: Optional[float] = Field(None, description="Time taken for synthesis in seconds")
