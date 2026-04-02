import uuid
from datetime import datetime

from pydantic import BaseModel


class HistoryResponse(BaseModel):
    id: uuid.UUID
    voice_id: uuid.UUID | None
    engine: str
    text: str
    language: str
    parameters: dict
    audio_duration_sec: float | None
    latency_ms: int | None
    total_time_ms: int | None
    sample_rate: int
    status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryListResponse(BaseModel):
    items: list[HistoryResponse]
    total: int
    page: int
    page_size: int
