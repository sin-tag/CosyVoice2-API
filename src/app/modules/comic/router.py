import json
import logging
import os
import time
import uuid

import aiofiles
from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import Response

from app.core.config import settings
from app.core.dependencies import DB, ApiKey
from app.core.exceptions import AppError
from app.engine.registry import engine_registry
from app.modules.comic import service
from app.modules.comic.schemas import ComicDubbingResponse, DialogueSegment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/comic", tags=["comic-dubbing"])


async def _save_temp_audio(file: UploadFile, speaker: str) -> str:
    os.makedirs(settings.voices_storage_path, exist_ok=True)
    ext = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    path = f"{settings.voices_storage_path}/temp_{uuid.uuid4().hex[:8]}_{speaker}{ext}"
    async with aiofiles.open(path, "wb") as f:
        await f.write(await file.read())
    return path


async def _parse_and_generate(
    db, script: str, language: str, uploads: dict[str, UploadFile | None],
    temperature: float, top_p: float, top_k: int, repetition_penalty: float,
):
    """Shared logic: parse script, save audio files, generate, cleanup."""
    try:
        raw_segments = json.loads(script)
        segments = [DialogueSegment(**seg).model_dump() for seg in raw_segments]
    except (json.JSONDecodeError, Exception) as e:
        raise AppError(400, f"Invalid script JSON: {e}", error_code="invalid_script")

    if not segments:
        raise AppError(400, "Script must have at least 1 segment", error_code="empty_script")

    script_speakers = set(seg["speaker"] for seg in segments)
    speaker_refs: dict[str, str] = {}
    temp_files: list[str] = []

    try:
        for speaker in script_speakers:
            file = uploads.get(speaker)
            if file is None:
                raise AppError(400, f"Missing audio file for speaker '{speaker}'", error_code="missing_voice_file")
            path = await _save_temp_audio(file, speaker)
            speaker_refs[speaker] = path
            temp_files.append(path)

        wav_bytes, sr, duration_sec, history_id = await service.generate_comic_audio(
            db, segments, speaker_refs, language,
            temperature=temperature, top_p=top_p, top_k=top_k,
            repetition_penalty=repetition_penalty,
        )
        return wav_bytes, sr, duration_sec, history_id, segments
    finally:
        for path in temp_files:
            try:
                os.remove(path)
            except OSError:
                pass


@router.post("/dub", response_model=ComicDubbingResponse)
async def comic_dub(
    db: DB,
    _: ApiKey,
    script: str = Form(..., description='JSON: [{"speaker":"narrator","text":"..."},...]'),
    language: str = Form("en"),
    temperature: float = Form(0.7),
    top_p: float = Form(0.9),
    top_k: int = Form(50),
    repetition_penalty: float = Form(1.2),
    narrator: UploadFile | None = None,
    char1: UploadFile | None = None,
    char2: UploadFile | None = None,
    char3: UploadFile | None = None,
    char4: UploadFile | None = None,
):
    """Generate dubbed audio for a comic/story.

    Upload voice reference audio for each speaker.
    Each segment is generated individually with Qwen voice clone, then concatenated.

    curl -X POST /api/v1/comic/dub \\
      -H "X-Api-Key: ..." \\
      -F 'script=[{"speaker":"narrator","text":"Dark night..."},{"speaker":"char1","text":"Stop!"}]' \\
      -F language=en \\
      -F narrator=@narrator.wav \\
      -F char1=@hero_voice.wav
    """
    start = time.perf_counter()
    uploads = {"narrator": narrator, "char1": char1, "char2": char2, "char3": char3, "char4": char4}

    wav_bytes, sr, duration_sec, history_id, segments = await _parse_and_generate(
        db, script, language, uploads, temperature, top_p, top_k, repetition_penalty,
    )

    speakers = list(dict.fromkeys(seg["speaker"] for seg in segments))
    slots = engine_registry.gpu_slots("qwen")

    return ComicDubbingResponse(
        success=True,
        message=f"Comic dubbing completed: {len(segments)} segments, {len(speakers)} speakers",
        audio_url=f"/api/v1/comic/audio/{history_id}",
        duration=round(duration_sec, 2),
        synthesis_time=round(time.perf_counter() - start, 3),
        sample_rate=sr,
        history_id=str(history_id),
        speakers=speakers,
        segments_count=len(segments),
        gpu_slots_free=slots["free"],
        gpu_slots_total=slots["total"],
    )


@router.post("/dub/audio")
async def comic_dub_audio(
    db: DB,
    _: ApiKey,
    script: str = Form(..., description='JSON: [{"speaker":"narrator","text":"..."},...]'),
    language: str = Form("en"),
    temperature: float = Form(0.7),
    top_p: float = Form(0.9),
    top_k: int = Form(50),
    repetition_penalty: float = Form(1.2),
    narrator: UploadFile | None = None,
    char1: UploadFile | None = None,
    char2: UploadFile | None = None,
    char3: UploadFile | None = None,
    char4: UploadFile | None = None,
):
    """Generate dubbed audio — returns raw WAV bytes."""
    uploads = {"narrator": narrator, "char1": char1, "char2": char2, "char3": char3, "char4": char4}

    wav_bytes, sr, duration_sec, history_id, _ = await _parse_and_generate(
        db, script, language, uploads, temperature, top_p, top_k, repetition_penalty,
    )

    slots = engine_registry.gpu_slots("qwen")
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
