from pydantic import BaseModel, Field


class DialogueSegment(BaseModel):
    """A single line in the comic script."""
    speaker: str = Field(..., description="Speaker name: 'narrator', 'char1', 'char2', etc.")
    text: str = Field(..., max_length=2000)


class ComicDubbingResponse(BaseModel):
    """Standard response for comic dubbing generation."""
    success: bool
    message: str
    audio_url: str | None = None
    duration: float | None = None
    synthesis_time: float | None = None
    sample_rate: int = 24000
    history_id: str | None = None
    speakers: list[str] = []
    segments_count: int = 0
    gpu_slots_free: int | None = None
    gpu_slots_total: int | None = None
