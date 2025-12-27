"""
Synthesis engine for Chatterbox TTS API
Handles voice synthesis operations with Chatterbox specific features
"""

import os
import asyncio
import logging
import uuid
import time
from typing import Optional, Generator, Any, Dict

import torch
import torchaudio

from app.core.voice_manager_chatterbox import VoiceManagerChatterbox
from app.models.synthesis import (
    CrossLingualWithAudioRequest, CrossLingualWithCacheRequest,
    SynthesisResponse, AudioFormat
)
from app.core.config import settings
from app.core.exceptions import SynthesisError, VoiceNotFoundError, ModelNotReadyError
from app.utils.file_utils import file_manager
from app.utils.audio import audio_processor

logger = logging.getLogger(__name__)

# Audio processing constants
MAX_VAL = 0.8
CHATTERBOX_SAMPLE_RATE = 24000  # Chatterbox uses 24kHz


def postprocess(speech, sample_rate=24000):
    """Postprocess audio for better quality"""
    import librosa

    # Trim silence
    speech_np = speech.numpy() if isinstance(speech, torch.Tensor) else speech
    speech_trimmed, _ = librosa.effects.trim(speech_np, top_db=60)
    speech = torch.tensor(speech_trimmed, dtype=torch.float32)

    # Normalize
    if speech.abs().max() > MAX_VAL:
        speech = speech / speech.abs().max() * MAX_VAL

    # Add padding
    if speech.dim() == 1:
        speech = speech.unsqueeze(0)

    padding = torch.zeros(1, int(sample_rate * 0.2))
    speech = torch.cat([speech, padding], dim=1)

    return speech


class SynthesisEngineChatterbox:
    """Voice synthesis engine for Chatterbox TTS"""

    def __init__(self, voice_manager: VoiceManagerChatterbox):
        self.voice_manager = voice_manager

    async def synthesize_cross_lingual_with_audio(
        self,
        request: CrossLingualWithAudioRequest,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        language: str = "en"
    ) -> SynthesisResponse:
        """
        Voice cloning synthesis with audio file

        Args:
            request: Synthesis request with text and audio reference
            exaggeration: How much to exaggerate the voice characteristics (0.0-1.0)
            cfg_weight: Classifier-free guidance weight for original model (0.0-1.0)
            language: Language code for multilingual model (e.g., "en", "zh", "ja")
        """
        try:
            model = self.voice_manager._get_active_model()
            if not model:
                raise ModelNotReadyError("Chatterbox model not ready")

            prompt_audio_path = await self._resolve_audio_path(request.prompt_audio_url)
            if not os.path.exists(prompt_audio_path):
                raise FileNotFoundError(f"Prompt audio file not found: {prompt_audio_path}")

            output_filename = f"chatterbox_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)
            file_manager.ensure_directory_exists(os.path.dirname(output_path))

            synthesis_time = await self._synthesize_with_reference(
                model=model,
                text=request.text,
                prompt_audio_path=prompt_audio_path,
                output_path=output_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                language=language
            )

            duration = await self._get_audio_duration(output_path)

            return SynthesisResponse(
                success=True,
                message="Chatterbox synthesis completed",
                audio_url=f"/api/v4/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )

        except Exception as e:
            logger.error(f"Error in Chatterbox synthesis with audio: {e}")
            raise SynthesisError(f"Chatterbox synthesis failed: {str(e)}")

    async def synthesize_cross_lingual_with_cache(
        self,
        request: CrossLingualWithCacheRequest,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        language: str = "en"
    ) -> SynthesisResponse:
        """Voice cloning synthesis with cached voice"""
        try:
            model = self.voice_manager.get_model_directly()
            if not model:
                raise ModelNotReadyError("Chatterbox model not ready")

            cached_voice = await self.voice_manager.get_voice(request.voice_id)
            if not cached_voice:
                raise VoiceNotFoundError(f"Cached voice '{request.voice_id}' not found")

            audio_path = cached_voice.audio_file_path
            if not audio_path:
                raise VoiceNotFoundError(f"Audio file for voice '{request.voice_id}' not found")

            # Convert relative path to absolute if needed
            if not os.path.isabs(audio_path):
                audio_path = os.path.abspath(audio_path)

            if not os.path.exists(audio_path):
                raise VoiceNotFoundError(f"Audio file for voice '{request.voice_id}' not found at: {audio_path}")

            output_filename = f"chatterbox_cache_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)
            file_manager.ensure_directory_exists(os.path.dirname(output_path))

            synthesis_time = await self._synthesize_with_reference(
                model=model,
                text=request.text,
                prompt_audio_path=audio_path,
                output_path=output_path,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                language=language
            )

            duration = await self._get_audio_duration(output_path)

            return SynthesisResponse(
                success=True,
                message="Chatterbox synthesis completed",
                audio_url=f"/api/v4/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )

        except Exception as e:
            logger.error(f"Error in Chatterbox synthesis with cache: {e}")
            raise SynthesisError(f"Chatterbox synthesis failed: {str(e)}")

    async def synthesize_with_emotion_tags(
        self,
        text: str,
        prompt_audio_path: str,
        output_path: str,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5
    ) -> float:
        """
        Synthesis with emotion/paralinguistic tags

        Supported tags: [laugh], [cough], [sigh], [gasp], [clear throat], etc.
        """
        return await self._synthesize_with_reference(
            model=self.voice_manager._get_active_model(),
            text=text,
            prompt_audio_path=prompt_audio_path,
            output_path=output_path,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight
        )

    async def _synthesize_with_reference(
        self,
        model,
        text: str,
        prompt_audio_path: str,
        output_path: str,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        language: str = "en"
    ) -> float:
        """Core synthesis with reference audio"""
        start_time = time.time()
        model_type = self.voice_manager.model_type

        def _sync_synthesis():
            import torchaudio as ta

            if model_type == "multilingual":
                # ChatterboxMultilingualTTS.generate(text, language_id=..., audio_prompt_path=...)
                wav = model.generate(
                    text,
                    language_id=language,
                    audio_prompt_path=prompt_audio_path
                )
            else:
                # ChatterboxTTS.generate(text, audio_prompt_path=..., exaggeration=..., cfg_weight=...)
                wav = model.generate(
                    text,
                    audio_prompt_path=prompt_audio_path,
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight
                )

            # Save using model's sample rate
            ta.save(output_path, wav, model.sr)

            return time.time() - start_time

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def synthesize_multilingual(
        self,
        text: str,
        prompt_audio_path: str,
        output_path: str,
        language: str = "en",
        exaggeration: float = 0.5
    ) -> float:
        """
        Multilingual synthesis (requires ChatterboxMultilingual model)

        Args:
            text: Text to synthesize
            prompt_audio_path: Path to reference audio (optional for multilingual)
            output_path: Path to save output
            language: Target language code (e.g., "en", "zh", "ja", "ko", etc.)
            exaggeration: Voice exaggeration factor
        """
        start_time = time.time()

        def _sync_synthesis():
            import torchaudio as ta

            model = self.voice_manager._get_active_model()
            if self.voice_manager.model_type != "multilingual":
                raise ValueError("Multilingual synthesis requires ChatterboxMultilingual model")

            # ChatterboxMultilingualTTS.generate(text, language_id=..., audio_prompt_path=...)
            if prompt_audio_path and os.path.exists(prompt_audio_path):
                wav = model.generate(
                    text,
                    language_id=language,
                    audio_prompt_path=prompt_audio_path
                )
            else:
                wav = model.generate(
                    text,
                    language_id=language
                )

            # Save using model's sample rate
            ta.save(output_path, wav, model.sr)

            return time.time() - start_time

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def _resolve_audio_path(self, audio_url: str) -> str:
        """Resolve audio URL to local file path"""
        if os.path.exists(audio_url):
            return audio_url

        if audio_url.startswith('/api/v4/audio/'):
            filename = audio_url.split('/')[-1]
            return file_manager.get_output_audio_path(filename)

        if not os.path.isabs(audio_url):
            return os.path.abspath(audio_url)

        return audio_url

    async def _get_audio_duration(self, audio_path: str) -> Optional[float]:
        """Get audio file duration"""
        try:
            audio_info = await audio_processor._get_audio_info(audio_path)
            return audio_info[0] if audio_info else None
        except Exception:
            return None

    def get_capabilities(self) -> Dict[str, Any]:
        """Get Chatterbox capabilities based on loaded model"""
        model_type = self.voice_manager.model_type

        capabilities = {
            "model_type": model_type,
            "sample_rate": CHATTERBOX_SAMPLE_RATE,
            "features": {
                "voice_cloning": True,
                "paralinguistic_tags": True,  # [laugh], [cough], etc.
                "watermarking": True,  # Perth watermark
            },
            "parameters": {
                "exaggeration": {
                    "description": "How much to exaggerate voice characteristics",
                    "min": 0.0,
                    "max": 1.0,
                    "default": 0.5
                }
            },
            "supported_tags": [
                "[laugh]", "[cough]", "[sigh]", "[gasp]",
                "[clear throat]", "[inhale]", "[exhale]"
            ]
        }

        if model_type == "turbo":
            capabilities["description"] = "Fast voice agent model (350M params)"
            capabilities["languages"] = ["en"]
        elif model_type == "multilingual":
            capabilities["description"] = "Multilingual model (500M params, 23+ languages)"
            capabilities["languages"] = self.voice_manager.get_supported_languages()
            capabilities["features"]["multilingual"] = True
        else:  # original
            capabilities["description"] = "Original model with CFG control (500M params)"
            capabilities["languages"] = ["en"]
            capabilities["parameters"]["cfg_weight"] = {
                "description": "Classifier-free guidance weight",
                "min": 0.0,
                "max": 1.0,
                "default": 0.5
            }
            capabilities["features"]["cfg_control"] = True

        return capabilities
