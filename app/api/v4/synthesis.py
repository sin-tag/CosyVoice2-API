"""
Synthesis endpoints for Chatterbox TTS (v4)
Voice cloning synthesis with paralinguistic tags support
"""

from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Request

from app.models.synthesis import (
    CrossLingualWithAudioRequest, CrossLingualWithCacheRequest,
    SynthesisResponse, AudioFormat
)
from app.core.voice_manager_chatterbox import VoiceManagerChatterbox
from app.core.synthesis_engine_chatterbox import SynthesisEngineChatterbox
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
                cfg_weight=cfg_weight
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
            cfg_weight=cfg_weight
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
            # Use cached voice
            cached_voice = await voice_manager.get_voice(voice_id)
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
