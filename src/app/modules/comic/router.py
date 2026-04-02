import logging
import time

from fastapi import APIRouter
from fastapi.responses import Response

from app.core.dependencies import DB, ApiKey
from app.engine.registry import engine_registry
from app.modules.comic import service
from app.modules.comic.schemas import ComicDubbingRequest, ComicDubbingResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/comic", tags=["comic-dubbing"])


@router.post("/dub", response_model=ComicDubbingResponse)
async def comic_dub(body: ComicDubbingRequest, db: DB, _: ApiKey):
    """Generate dubbed audio for a comic/story script.

    Sends segments with speaker assignments and voice references.
    Returns synthesis metadata (use /dub/audio for raw WAV).
    """
    start = time.perf_counter()

    segments = [seg.model_dump() for seg in body.segments]
    voice_ids = body.voices

    wav_bytes, sr, duration_sec, history_id = await service.generate_comic_audio(
        db, segments, voice_ids, body.language,
        temperature=body.temperature,
        top_p=body.top_p,
        top_k=body.top_k,
        repetition_penalty=body.repetition_penalty,
        max_new_tokens=body.max_new_tokens,
    )

    synthesis_time = round(time.perf_counter() - start, 3)
    speakers = list(dict.fromkeys(seg["speaker"] for seg in segments))
    slots = engine_registry.gpu_slots("moss")

    return ComicDubbingResponse(
        success=True,
        message=f"Comic dubbing completed: {len(segments)} segments, {len(speakers)} speakers",
        audio_url=f"/api/v1/comic/audio/{history_id}",
        duration=round(duration_sec, 2),
        synthesis_time=synthesis_time,
        sample_rate=sr,
        history_id=str(history_id),
        speakers=speakers,
        segments_count=len(segments),
        gpu_slots_free=slots["free"],
        gpu_slots_total=slots["total"],
    )


@router.post("/dub/audio")
async def comic_dub_audio(body: ComicDubbingRequest, db: DB, _: ApiKey):
    """Generate dubbed audio and return raw WAV bytes (for direct playback)."""
    segments = [seg.model_dump() for seg in body.segments]

    wav_bytes, sr, duration_sec, history_id = await service.generate_comic_audio(
        db, segments, body.voices, body.language,
        temperature=body.temperature,
        top_p=body.top_p,
        top_k=body.top_k,
        repetition_penalty=body.repetition_penalty,
        max_new_tokens=body.max_new_tokens,
    )

    slots = engine_registry.gpu_slots("moss")
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "X-History-Id": str(history_id),
            "X-Sample-Rate": str(sr),
            "X-Duration": str(round(duration_sec, 2)),
            "X-GPU-Slots-Free": str(slots["free"]),
            "X-GPU-Slots-Total": str(slots["total"]),
        },
    )
