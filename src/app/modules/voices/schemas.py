import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VoiceCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = None
    language: str = Field(..., max_length=10)
    reference_text: str | None = None


class VoiceUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = None
    language: str | None = Field(None, max_length=10)
    reference_text: str | None = None
    is_default: bool | None = None


class VoiceResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    language: str
    reference_text: str | None
    audio_duration_sec: float
    moss_compatible: bool
    qwen_compatible: bool
    moss_cached: bool
    qwen_cached: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VoiceListResponse(BaseModel):
    items: list[VoiceResponse]
    total: int
    page: int
    page_size: int
