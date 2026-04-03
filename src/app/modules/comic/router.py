import json
import logging
import os
import time
import uuid

import aiofiles
from fastapi import APIRouter, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import DB, ApiKey
from app.core.exceptions import AppError, VoiceNotFoundError
from app.engine.registry import engine_registry
from app.models.voice import Voice
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


async def _resolve_speaker_refs(
    db: AsyncSession,
    script_speakers: set[str],
    uploads: dict[str, UploadFile | None],
    voice_ids: dict[str, str],
) -> tuple[dict[str, str], list[str]]:
    """Resolve speaker → audio path from uploads OR voice_ids.

    Priority: uploaded file > voice_id from DB.
    Returns: (speaker_refs, temp_files_to_cleanup)
    """
    speaker_refs: dict[str, str] = {}
    speaker_ref_texts: dict[str, str] = {}
    temp_files: list[str] = []

    for speaker in script_speakers:
        # 1. Check uploaded file first
        file = uploads.get(speaker)
        if file is not None:
            path = await _save_temp_audio(file, speaker)
            speaker_refs[speaker] = path
            temp_files.append(path)
            continue

        # 2. Check voice_id from DB
        vid = voice_ids.get(speaker)
        if vid:
            voice = await db.get(Voice, str(vid))
            if voice is None:
                raise VoiceNotFoundError(str(vid))
            speaker_refs[speaker] = voice.reference_audio_path
            if voice.reference_text:
                speaker_ref_texts[speaker] = voice.reference_text
            continue

        # 3. Neither provided
        raise AppError(
            400,
            f"Missing voice for speaker '{speaker}': upload a file or provide a voice_id",
            error_code="missing_voice",
        )

    return speaker_refs, speaker_ref_texts, temp_files


async def _parse_and_generate(
    db: AsyncSession,
    script: str,
    language: str,
    uploads: dict[str, UploadFile | None],
    voice_ids_json: str | None,
    temperature: float,
    top_p: float,
    top_k: int,
    repetition_penalty: float,
):
    """Shared logic: parse script, resolve voices, generate, cleanup."""
    # Parse script
    try:
        raw_segments = json.loads(script)
        segments = [DialogueSegment(**seg).model_dump() for seg in raw_segments]
    except (json.JSONDecodeError, Exception) as e:
        raise AppError(400, f"Invalid script JSON: {e}", error_code="invalid_script")

    if not segments:
        raise AppError(400, "Script must have at least 1 segment", error_code="empty_script")

    # Parse voice_ids JSON
    voice_ids: dict[str, str] = {}
    if voice_ids_json:
        try:
            voice_ids = json.loads(voice_ids_json)
        except json.JSONDecodeError as e:
            raise AppError(400, f"Invalid voice_ids JSON: {e}", error_code="invalid_voice_ids")

    script_speakers = set(seg["speaker"] for seg in segments)
    speaker_refs, speaker_ref_texts, temp_files = await _resolve_speaker_refs(db, script_speakers, uploads, voice_ids)

    try:
        wav_bytes, sr, duration_sec, history_id = await service.generate_comic_audio(
            db, segments, speaker_refs, language,
            speaker_ref_texts=speaker_ref_texts,
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
    voice_ids: str | None = Form(None, description='JSON: {"narrator":"voice-uuid","char1":"voice-uuid"}'),
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

    Two ways to provide voice for each speaker (can mix both):
    1. Upload audio file directly: narrator=@voice.wav
    2. Use pre-uploaded voice_id: voice_ids={"narrator":"uuid","char1":"uuid"}

    Uploaded files take priority over voice_ids.

    Examples:
        # All files:
        curl -F narrator=@narrator.wav -F char1=@hero.wav ...

        # All voice_ids:
        curl -F 'voice_ids={"narrator":"uuid1","char1":"uuid2"}' ...

        # Mix: narrator from file, char1 from DB:
        curl -F narrator=@narrator.wav -F 'voice_ids={"char1":"uuid"}' ...
    """
    start = time.perf_counter()
    uploads = {"narrator": narrator, "char1": char1, "char2": char2, "char3": char3, "char4": char4}

    wav_bytes, sr, duration_sec, history_id, segments = await _parse_and_generate(
        db, script, language, uploads, voice_ids, temperature, top_p, top_k, repetition_penalty,
    )

    speakers = list(dict.fromkeys(seg["speaker"] for seg in segments))
    slots = engine_registry.gpu_slots("omni")

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
    voice_ids: str | None = Form(None, description='JSON: {"narrator":"voice-uuid","char1":"voice-uuid"}'),
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
        db, script, language, uploads, voice_ids, temperature, top_p, top_k, repetition_penalty,
    )

    slots = engine_registry.gpu_slots("omni")
    return Response(
        content=wav_bytes,
        media_type="audio/mpeg",
        headers={
            "X-History-Id": str(history_id),
            "X-Sample-Rate": str(sr),
            "X-Duration": str(round(duration_sec, 2)),
            "X-GPU-Slots-Free": str(slots["free"]),
            "X-GPU-Slots-Total": str(slots["total"]),
        },
    )


@router.get("/audio/{history_id}")
async def download_comic_audio(db: DB, _: ApiKey, history_id: str):
    """Download previously generated comic dubbing audio by history_id."""
    from app.models.generation import GenerationHistory
    record = await db.get(GenerationHistory, history_id)
    if record is None or not record.audio_path:
        raise AppError(404, f"Audio not found for history '{history_id}'", error_code="audio_not_found")

    if not os.path.exists(record.audio_path):
        raise AppError(404, "Audio file missing from disk", error_code="audio_not_found")

    async with aiofiles.open(record.audio_path, "rb") as f:
        content = await f.read()

    return Response(
        content=content,
        media_type="audio/mpeg",
        headers={
            "X-History-Id": history_id,
            "X-Sample-Rate": str(record.sample_rate or 24000),
            "X-Duration": str(round(record.audio_duration_sec or 0, 2)),
        },
    )
