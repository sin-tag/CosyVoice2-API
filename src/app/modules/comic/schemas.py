import uuid

from pydantic import BaseModel, Field


class DialogueSegment(BaseModel):
    """A single line in the comic script."""
    speaker: str = Field(..., description="Speaker name: 'narrator', 'char1', 'char2', etc.")
    text: str = Field(..., max_length=2000, description="Text for this speaker to say")


class ComicDubbingRequest(BaseModel):
    """Request to generate dubbed audio for a comic/story.

    Example:
    {
        "segments": [
            {"speaker": "narrator", "text": "In a dark night..."},
            {"speaker": "char1", "text": "Stop! Who goes there?"},
            {"speaker": "char2", "text": "I'm just a traveler."},
            {"speaker": "narrator", "text": "The stranger stepped forward..."},
            {"speaker": "char1", "text": "State your name!"}
        ],
        "voices": {
            "narrator": "uuid-of-uploaded-voice",
            "char1": "uuid-of-uploaded-voice",
            "char2": "uuid-of-uploaded-voice"
        },
        "language": "en"
    }
    """
    segments: list[DialogueSegment] = Field(..., min_length=1, max_length=100)
    voices: dict[str, uuid.UUID] = Field(
        ...,
        description="Map speaker name → voice_id (from uploaded voices)",
    )
    language: str = Field("en", max_length=10)
    temperature: float = Field(1.1, ge=0.0, le=2.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0)
    top_k: int = Field(50, ge=1, le=500)
    repetition_penalty: float = Field(1.1, ge=1.0, le=3.0)
    max_new_tokens: int = Field(2000, ge=100, le=10000)


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
