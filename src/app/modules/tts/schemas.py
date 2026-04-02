import uuid

from pydantic import BaseModel, Field


# ──── Request Schemas ────


class TTSGenerateRequest(BaseModel):
    text: str = Field(..., max_length=5000)
    language: str = Field(..., max_length=10)
    voice_id: uuid.UUID | None = None
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0)
    top_k: int = Field(50, ge=1, le=500)
    repetition_penalty: float = Field(1.2, ge=1.0, le=3.0)
    output_format: str = Field("wav", pattern="^(wav|pcm)$")


class TTSStreamRequest(BaseModel):
    text: str = Field(..., max_length=5000)
    language: str = Field(..., max_length=10)
    voice_id: uuid.UUID | None = None
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0)
    top_k: int = Field(50, ge=1, le=500)
    repetition_penalty: float = Field(1.2, ge=1.0, le=3.0)

    def generation_params(self) -> dict:
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
        }


# ──── Response Schemas (aligned with chatterbox branch) ────


class SynthesisResponse(BaseModel):
    """Standard synthesis response — matches chatterbox branch format."""
    success: bool
    message: str
    audio_url: str | None = None
    duration: float | None = None
    format: str = "wav"
    synthesis_time: float | None = None
    sample_rate: int = 24000
    history_id: str | None = None
    gpu_slots_free: int | None = None
    gpu_slots_total: int | None = None


class EngineInfoResponse(BaseModel):
    name: str
    loaded: bool
    languages: list[str]
    cached_voices: int
    gpu_slots: dict | None = None


class LanguageListResponse(BaseModel):
    engine: str
    languages: list[str]
