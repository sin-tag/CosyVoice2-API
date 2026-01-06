"""
Synthesis endpoints for Chatterbox TTS (v4)
Voice cloning synthesis with paralinguistic tags support
"""

import asyncio
import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Request, BackgroundTasks

from app.models.synthesis import (
    CrossLingualWithAudioRequest, CrossLingualWithCacheRequest,
    SynthesisResponse, AudioFormat
)
from app.core.voice_manager_chatterbox import VoiceManagerChatterbox
from app.core.synthesis_engine_chatterbox import SynthesisEngineChatterbox
from app.core.async_task_manager import (
    get_task_manager, AsyncTaskManager, SynthesisTask, TaskStatus
)
from app.core.exceptions import SynthesisError, VoiceNotFoundError, ModelNotReadyError
from app.utils.file_utils import file_manager

router = APIRouter(prefix="/synthesis", tags=["Chatterbox Synthesis (v4)"])


def get_voice_manager_chatterbox(request: Request) -> VoiceManagerChatterbox:
    """Get Chatterbox voice manager from app state"""
    if not hasattr(request.app.state, 'voice_manager_chatterbox'):
        raise HTTPException(status_code=503, detail="Chatterbox voice manager not ready")
    return request.app.state.voice_manager_chatterbox


def get_synthesis_engine_chatterbox(request: Request) -> SynthesisEngineChatterbox:
    """Get Chatterbox synthesis engine from app state"""
    if not hasattr(request.app.state, 'synthesis_engine_chatterbox'):
        raise HTTPException(status_code=503, detail="Chatterbox synthesis engine not ready")
    return request.app.state.synthesis_engine_chatterbox


@router.post("/with-audio", response_model=SynthesisResponse, summary="Synthesize with audio reference")
async def synthesize_with_audio(
    text: str = Form(..., description="Text to synthesize. Supports tags like [laugh], [cough]"),
    prompt_audio: UploadFile = File(..., description="Reference audio file for voice cloning"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    exaggeration: float = Form(0.5, ge=0.0, le=1.0, description="Voice exaggeration factor"),
    cfg_weight: float = Form(0.5, ge=0.0, le=1.0, description="CFG weight (original model only)"),
    language: str = Form("en", description="Language code for multilingual model (e.g., en, zh, ja, ko)"),
    synthesis_engine: SynthesisEngineChatterbox = Depends(get_synthesis_engine_chatterbox)
):
    """
    Synthesize speech with voice cloning using an audio reference.

    ## Paralinguistic Tags
    You can include emotion/action tags in the text:
    - `[laugh]` - Add laughter
    - `[cough]` - Add cough sound
    - `[sigh]` - Add sighing
    - `[gasp]` - Add gasping
    - `[clear throat]` - Clear throat sound

    Example: "Hello there! [laugh] That was funny."

    ## Parameters
    - **exaggeration**: How much to exaggerate voice characteristics (0.0-1.0)
    - **cfg_weight**: Classifier-free guidance weight (only for original model)
    - **language**: Language code for multilingual model (default: "en")
    """
    try:
        # Save uploaded audio to temp file
        audio_content = await prompt_audio.read()
        temp_path = await file_manager.save_temp_file(
            audio_content, prompt_audio.filename or "prompt.wav"
        )

        try:
            request = CrossLingualWithAudioRequest(
                text=text,
                prompt_audio_url=temp_path,
                format=format,
                speed=1.0,
                stream=False
            )

            result = await synthesis_engine.synthesize_cross_lingual_with_audio(
                request=request,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                language=language
            )

            return result

        finally:
            # Cleanup temp file
            file_manager.delete_file(temp_path)

    except ModelNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


@router.post("/with-cache", response_model=SynthesisResponse, summary="Synthesize with cached voice")
async def synthesize_with_cache(
    text: str = Form(..., description="Text to synthesize. Supports tags like [laugh], [cough]"),
    voice_id: str = Form(..., description="Cached voice ID"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    exaggeration: float = Form(0.5, ge=0.0, le=1.0, description="Voice exaggeration factor"),
    cfg_weight: float = Form(0.5, ge=0.0, le=1.0, description="CFG weight (original model only)"),
    language: str = Form("en", description="Language code for multilingual model (e.g., en, zh, ja, ko)"),
    synthesis_engine: SynthesisEngineChatterbox = Depends(get_synthesis_engine_chatterbox)
):
    """
    Synthesize speech using a previously cached voice.

    ## Paralinguistic Tags
    Include emotion/action tags in the text:
    - `[laugh]`, `[cough]`, `[sigh]`, `[gasp]`, `[clear throat]`

    Example: "I can't believe it! [gasp] That's amazing!"
    """
    try:
        request = CrossLingualWithCacheRequest(
            text=text,
            voice_id=voice_id,
            format=format,
            speed=1.0,
            stream=False
        )

        result = await synthesis_engine.synthesize_cross_lingual_with_cache(
            request=request,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            language=language
        )

        return result

    except VoiceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ModelNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


@router.post("/multilingual", response_model=SynthesisResponse, summary="Multilingual synthesis")
async def synthesize_multilingual(
    request: Request,
    text: str = Form(..., description="Text to synthesize"),
    voice_id: Optional[str] = Form(None, description="Cached voice ID (use this OR prompt_audio)"),
    language: str = Form("en", description="Target language code (e.g., en, zh, ja, ko)"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    exaggeration: float = Form(0.5, ge=0.0, le=1.0, description="Voice exaggeration factor"),
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox),
    synthesis_engine: SynthesisEngineChatterbox = Depends(get_synthesis_engine_chatterbox)
):
    """
    Multilingual voice synthesis (requires ChatterboxMultilingual model).

    You can provide either:
    - **voice_id**: Use a cached voice from the voice library
    - **prompt_audio**: Upload a new audio file for voice cloning (multipart form-data)

    Supports 23+ languages including:
    - en (English), zh (Chinese), ja (Japanese), ko (Korean)
    - de (German), es (Spanish), fr (French), it (Italian), ru (Russian)
    - pt (Portuguese), pl (Polish), nl (Dutch), ar (Arabic), tr (Turkish)
    - And more...
    """
    if voice_manager.model_type != "multilingual":
        raise HTTPException(
            status_code=400,
            detail="Multilingual synthesis requires ChatterboxMultilingual model. "
                   f"Current model: {voice_manager.model_type}"
        )

    # Validate language code
    supported_languages = voice_manager.get_language_codes()
    if language not in supported_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language code: '{language}'. Supported: {', '.join(sorted(supported_languages))}"
        )

    # Try to get prompt_audio from form data
    form = await request.form()
    prompt_audio = form.get("prompt_audio")

    # Check if prompt_audio is a valid file upload (not empty string)
    has_prompt_audio = prompt_audio and hasattr(prompt_audio, 'read') and hasattr(prompt_audio, 'filename')

    # Must provide either voice_id or prompt_audio
    if not voice_id and not has_prompt_audio:
        raise HTTPException(
            status_code=400,
            detail="Must provide either voice_id or prompt_audio"
        )

    temp_path = None
    try:
        import uuid
        import os

        # Resolve audio path from voice_id or uploaded file
        if voice_id:
            # Use cached voice (support both voice_id and voice name)
            cached_voice = await voice_manager.get_voice_by_id_or_name(voice_id)
            if not cached_voice:
                raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")
            if not cached_voice.audio_file_path:
                raise HTTPException(status_code=404, detail=f"Audio file for voice '{voice_id}' not found")

            # Convert relative path to absolute if needed
            audio_path = cached_voice.audio_file_path
            if not os.path.isabs(audio_path):
                audio_path = os.path.abspath(audio_path)

            if not os.path.exists(audio_path):
                raise HTTPException(status_code=404, detail=f"Audio file for voice '{voice_id}' not found at: {audio_path}")
        elif has_prompt_audio:
            # Use uploaded audio
            audio_content = await prompt_audio.read()
            temp_path = await file_manager.save_temp_file(
                audio_content, prompt_audio.filename or "prompt.wav"
            )
            audio_path = temp_path
        else:
            raise HTTPException(status_code=400, detail="No valid audio source provided")

        output_filename = f"chatterbox_multilingual_{uuid.uuid4().hex[:8]}.{format.value}"
        output_path = file_manager.get_output_audio_path(output_filename)
        file_manager.ensure_directory_exists(os.path.dirname(output_path))

        synthesis_time = await synthesis_engine.synthesize_multilingual(
            text=text,
            prompt_audio_path=audio_path,
            output_path=output_path,
            language=language,
            exaggeration=exaggeration
        )

        duration = await synthesis_engine._get_audio_duration(output_path)

        return SynthesisResponse(
            success=True,
            message=f"Chatterbox multilingual synthesis completed (lang={language})",
            audio_url=f"/api/v4/audio/{output_filename}",
            file_path=output_path,
            duration=duration,
            format=format,
            synthesis_time=synthesis_time
        )

    except HTTPException:
        raise
    except ModelNotReadyError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except SynthesisError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")
    finally:
        # Cleanup temp file if used
        if temp_path:
            file_manager.delete_file(temp_path)


@router.get("/capabilities", summary="Get Chatterbox capabilities")
async def get_capabilities(
    synthesis_engine: SynthesisEngineChatterbox = Depends(get_synthesis_engine_chatterbox)
):
    """
    Get the capabilities of the loaded Chatterbox model.

    Returns information about:
    - Model type (turbo, multilingual, original)
    - Supported languages
    - Available features
    - Parameter ranges
    """
    return synthesis_engine.get_capabilities()


@router.get("/languages", summary="Get supported languages")
async def get_supported_languages(
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox)
):
    """
    Get list of supported language codes for multilingual synthesis.

    Returns a mapping of language codes to language names.
    """
    return {
        "model_type": voice_manager.model_type,
        "languages": voice_manager.get_supported_languages(),
        "language_codes": voice_manager.get_language_codes()
    }


@router.get("/tags", summary="Get supported paralinguistic tags")
async def get_supported_tags():
    """
    Get list of supported paralinguistic tags for Chatterbox.

    These tags can be inserted into the text to add emotions or actions.
    """
    return {
        "tags": [
            {
                "tag": "[laugh]",
                "description": "Add laughter to the speech"
            },
            {
                "tag": "[cough]",
                "description": "Add a cough sound"
            },
            {
                "tag": "[sigh]",
                "description": "Add a sighing sound"
            },
            {
                "tag": "[gasp]",
                "description": "Add a gasp of surprise"
            },
            {
                "tag": "[clear throat]",
                "description": "Add throat clearing sound"
            },
            {
                "tag": "[inhale]",
                "description": "Add an inhale breath sound"
            },
            {
                "tag": "[exhale]",
                "description": "Add an exhale breath sound"
            }
        ],
        "usage_example": "Hello there! [laugh] That was really funny. [sigh] Anyway, let's continue."
    }


# ============================================
# Async/Background Task Endpoints
# ============================================

@router.post("/multilingual/async", summary="Multilingual synthesis (background task)")
async def synthesize_multilingual_async(
    request: Request,
    background_tasks: BackgroundTasks,
    text: str = Form(..., description="Text to synthesize"),
    voice_id: Optional[str] = Form(None, description="Cached voice ID or name"),
    language: str = Form("en", description="Target language code (e.g., en, zh, ja, ko)"),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    exaggeration: float = Form(0.5, ge=0.0, le=1.0, description="Voice exaggeration factor"),
    voice_manager: VoiceManagerChatterbox = Depends(get_voice_manager_chatterbox),
    synthesis_engine: SynthesisEngineChatterbox = Depends(get_synthesis_engine_chatterbox)
):
    """
    Start multilingual synthesis as a background task.

    Returns immediately with a task_id that can be used to check status.

    Use GET /synthesis/tasks/{task_id} to check the task status.
    """
    if voice_manager.model_type != "multilingual":
        raise HTTPException(
            status_code=400,
            detail="Multilingual synthesis requires ChatterboxMultilingual model. "
                   f"Current model: {voice_manager.model_type}"
        )

    # Validate language code
    supported_languages = voice_manager.get_language_codes()
    if language not in supported_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language code: '{language}'. Supported: {', '.join(sorted(supported_languages))}"
        )

    # Try to get prompt_audio from form data
    form = await request.form()
    prompt_audio = form.get("prompt_audio")
    has_prompt_audio = prompt_audio and hasattr(prompt_audio, 'read') and hasattr(prompt_audio, 'filename')

    if not voice_id and not has_prompt_audio:
        raise HTTPException(
            status_code=400,
            detail="Must provide either voice_id or prompt_audio"
        )

    # Resolve audio path
    audio_path = None
    temp_audio_path = None

    if voice_id:
        cached_voice = await voice_manager.get_voice_by_id_or_name(voice_id)
        if not cached_voice:
            raise HTTPException(status_code=404, detail=f"Voice '{voice_id}' not found")
        if not cached_voice.audio_file_path:
            raise HTTPException(status_code=404, detail=f"Audio file for voice '{voice_id}' not found")

        audio_path = cached_voice.audio_file_path
        if not os.path.isabs(audio_path):
            audio_path = os.path.abspath(audio_path)

        if not os.path.exists(audio_path):
            raise HTTPException(status_code=404, detail=f"Audio file not found at: {audio_path}")

    elif has_prompt_audio:
        # Save uploaded audio to permanent temp location (will be cleaned up after synthesis)
        audio_content = await prompt_audio.read()
        temp_audio_path = await file_manager.save_temp_file(
            audio_content, f"async_{uuid.uuid4().hex[:8]}_{prompt_audio.filename or 'prompt.wav'}"
        )
        audio_path = temp_audio_path

    # Create task
    task_manager = get_task_manager()
    task = await task_manager.create_task(
        text=text,
        voice_id=voice_id,
        language=language,
        format=format.value,
        exaggeration=exaggeration
    )

    # Define the synthesis function
    async def run_synthesis():
        try:
            output_filename = f"chatterbox_async_{task.task_id}_{uuid.uuid4().hex[:8]}.{format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)
            file_manager.ensure_directory_exists(os.path.dirname(output_path))

            synthesis_time = await synthesis_engine.synthesize_multilingual(
                text=text,
                prompt_audio_path=audio_path,
                output_path=output_path,
                language=language,
                exaggeration=exaggeration
            )

            duration = await synthesis_engine._get_audio_duration(output_path)

            return {
                "audio_url": f"/api/v4/audio/{output_filename}",
                "file_path": output_path,
                "duration": duration,
                "synthesis_time": synthesis_time
            }
        finally:
            # Cleanup temp audio if used
            if temp_audio_path and os.path.exists(temp_audio_path):
                file_manager.delete_file(temp_audio_path)

    # Enqueue task for sequential processing (don't use background_tasks, use queue)
    await task_manager.enqueue_task(
        task.task_id,
        run_synthesis
    )

    return {
        "success": True,
        "task_id": task.task_id,
        "status": task.status.value,
        "queue_position": task.queue_position,
        "message": task.message,
        "check_status_url": f"/api/v4/synthesis/tasks/{task.task_id}"
    }


@router.get("/tasks/{task_id}", summary="Get task status")
async def get_task_status(task_id: str):
    """
    Get the status of a background synthesis task.

    Returns task details including:
    - status: queued, processing, completed, failed
    - queue_position: Position in queue (0 = processing now)
    - progress: 0.0-1.0
    - audio_url: URL to download audio (when completed)
    - error_message: Error details (when failed)
    """
    task_manager = get_task_manager()
    task = await task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "queue_position": task.queue_position,
        "progress": task.progress,
        "message": task.message,
        "text": task.text,
        "voice_id": task.voice_id,
        "language": task.language,
        "format": task.format,
        "audio_url": task.audio_url,
        "file_path": task.file_path,
        "duration": task.duration,
        "synthesis_time": task.synthesis_time,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }


@router.get("/tasks", summary="List all tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50
):
    """
    List all synthesis tasks.

    Optionally filter by status: pending, processing, completed, failed
    """
    task_manager = get_task_manager()

    filter_status = None
    if status:
        try:
            filter_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: pending, processing, completed, failed"
            )

    tasks = await task_manager.list_tasks(status=filter_status, limit=limit)

    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "status": t.status.value,
                "progress": t.progress,
                "message": t.message,
                "text": t.text[:50] + "..." if len(t.text) > 50 else t.text,
                "voice_id": t.voice_id,
                "language": t.language,
                "audio_url": t.audio_url,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None
            }
            for t in tasks
        ],
        "total": len(tasks)
    }
