"""
Synthesis engine for CosyVoice3 API
Handles voice synthesis operations with CosyVoice3 specific features
"""

import os
import asyncio
import logging
import uuid
import time
from typing import Optional, Generator, Any, Dict

import torch
import torchaudio
import librosa
from cosyvoice.utils.file_utils import load_wav
from cosyvoice.utils.common import set_all_random_seed

from app.core.voice_manager_v3 import VoiceManagerV3
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
PROMPT_SR = 16000

# CosyVoice3 specific system prompt
COSYVOICE3_SYSTEM_PROMPT = "You are a helpful assistant.<|endofprompt|>"


def postprocess(speech, sample_rate=22050, top_db=60, hop_length=220, win_length=440):
    """Postprocess audio exactly like in the original CosyVoice webui"""
    speech, _ = librosa.effects.trim(
        speech, top_db=top_db,
        frame_length=win_length,
        hop_length=hop_length
    )
    if speech.abs().max() > MAX_VAL:
        speech = speech / speech.abs().max() * MAX_VAL
    speech = torch.concat([speech, torch.zeros(1, int(sample_rate * 0.2))], dim=1)
    return speech


class SynthesisEngineV3:
    """Voice synthesis engine for CosyVoice3"""

    def __init__(self, voice_manager: VoiceManagerV3):
        self.voice_manager = voice_manager

    async def synthesize_cross_lingual_with_audio(self, request: CrossLingualWithAudioRequest) -> SynthesisResponse:
        """Cross-lingual voice cloning with audio file"""
        try:
            model = self.voice_manager._get_active_model()
            if not model:
                raise ModelNotReadyError("CosyVoice3 model not ready")

            prompt_audio_path = await self._resolve_audio_path(request.prompt_audio_url)
            if not os.path.exists(prompt_audio_path):
                raise FileNotFoundError(f"Prompt audio file not found: {prompt_audio_path}")

            output_filename = f"v3_cross_lingual_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)
            file_manager.ensure_directory_exists(os.path.dirname(output_path))

            if request.instruct_text:
                synthesis_time = await self._synthesize_with_instruct2(
                    model, request.text, prompt_audio_path,
                    request.instruct_text, output_path, request.speed, request.stream
                )
            else:
                synthesis_time = await self._synthesize_cross_lingual(
                    model, request.text, prompt_audio_path,
                    output_path, request.speed, request.stream
                )

            duration = await self._get_audio_duration(output_path)

            return SynthesisResponse(
                success=True,
                message="CosyVoice3 synthesis completed",
                audio_url=f"/api/v3/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )

        except Exception as e:
            logger.error(f"Error in CosyVoice3 cross-lingual synthesis with audio: {e}")
            raise SynthesisError(f"CosyVoice3 synthesis failed: {str(e)}")

    async def synthesize_cross_lingual_with_cache(self, request: CrossLingualWithCacheRequest) -> SynthesisResponse:
        """Cross-lingual voice cloning with cached voice"""
        try:
            model = self.voice_manager.get_model_directly()
            if not model:
                raise ModelNotReadyError("CosyVoice3 model not ready")

            cached_voice = await self.voice_manager.get_voice(request.voice_id)
            if not cached_voice:
                raise VoiceNotFoundError(f"Cached voice '{request.voice_id}' not found")

            output_filename = f"v3_cache_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)
            file_manager.ensure_directory_exists(os.path.dirname(output_path))

            synthesis_time = await self._synthesize_cross_lingual_cached(
                model, request.text, request.voice_id,
                output_path, request.speed, request.stream
            )

            duration = await self._get_audio_duration(output_path)

            return SynthesisResponse(
                success=True,
                message="CosyVoice3 synthesis completed",
                audio_url=f"/api/v3/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )

        except Exception as e:
            logger.error(f"Error in CosyVoice3 cross-lingual synthesis with cache: {e}")
            raise SynthesisError(f"CosyVoice3 synthesis failed: {str(e)}")

    async def _synthesize_with_instruct2(self, model, text: str, prompt_audio_path: str,
                                         instruct_text: str, output_path: str,
                                         speed: float, stream: bool) -> float:
        """CosyVoice3 instruct2 synthesis with instruction control"""
        start_time = time.time()

        def _sync_synthesis():
            prompt_speech_16k = postprocess(load_wav(prompt_audio_path, PROMPT_SR), model.sample_rate)
            set_all_random_seed(42)

            # CosyVoice3 uses inference_instruct2 with system prompt format
            if hasattr(model, 'inference_instruct2'):
                # Format instruction with system prompt for CosyVoice3
                formatted_instruct = f"{COSYVOICE3_SYSTEM_PROMPT}{instruct_text}"
                logger.info(f"Using CosyVoice3 inference_instruct2: instruct='{instruct_text[:50]}...'")
                synthesis_generator = model.inference_instruct2(
                    text, formatted_instruct, prompt_speech_16k, stream=stream, speed=speed
                )
            else:
                # Fallback to cross-lingual
                logger.info("inference_instruct2 not available, using cross-lingual fallback")
                synthesis_generator = model.inference_cross_lingual(
                    text, prompt_speech_16k, stream=stream, speed=speed
                )

            all_audio_data = []
            chunk_count = 0

            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunk = model_output['tts_speech'].numpy().flatten()
                    all_audio_data.extend(audio_chunk)
                    chunk_count += 1
                    logger.debug(f"Processed chunk {chunk_count}: {len(audio_chunk)} samples")

            if not all_audio_data:
                raise SynthesisError("No audio generated")

            final_audio = torch.tensor(all_audio_data, dtype=torch.float32).unsqueeze(0)
            logger.info(f"Final audio shape: {final_audio.shape}, chunks: {chunk_count}")

            torchaudio.save(output_path, final_audio.cpu(), model.sample_rate)
            return time.time() - start_time

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def _synthesize_cross_lingual(self, model, text: str, prompt_audio_path: str,
                                        output_path: str, speed: float, stream: bool) -> float:
        """Cross-lingual synthesis"""
        start_time = time.time()

        def _sync_synthesis():
            prompt_speech_16k = postprocess(load_wav(prompt_audio_path, PROMPT_SR), model.sample_rate)
            set_all_random_seed(42)

            logger.info(f"Using CosyVoice3 cross-lingual synthesis: text='{text[:50]}...'")

            if hasattr(model, 'inference_cross_lingual'):
                synthesis_generator = model.inference_cross_lingual(
                    text, prompt_speech_16k, stream=stream, speed=speed
                )
            else:
                synthesis_generator = model.inference_zero_shot(
                    text, "", prompt_speech_16k, stream=stream, speed=speed
                )

            all_audio_data = []
            chunk_count = 0

            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunk = model_output['tts_speech'].numpy().flatten()
                    all_audio_data.extend(audio_chunk)
                    chunk_count += 1

            if not all_audio_data:
                raise SynthesisError("No audio generated")

            final_audio = torch.tensor(all_audio_data, dtype=torch.float32).unsqueeze(0)
            torchaudio.save(output_path, final_audio.cpu(), model.sample_rate)
            return time.time() - start_time

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def _synthesize_cross_lingual_cached(self, model, text: str, voice_id: str,
                                               output_path: str, speed: float, stream: bool) -> float:
        """Cross-lingual synthesis with cached voice"""
        start_time = time.time()

        def _sync_synthesis():
            set_all_random_seed(42)

            voice = self.voice_manager.voice_cache.voices.get(voice_id)
            if voice and voice.audio_file_path:
                prompt_speech_16k = postprocess(load_wav(voice.audio_file_path, PROMPT_SR), model.sample_rate)

                logger.info(f"CosyVoice3 cross-lingual for voice '{voice_id}': text='{text[:50]}...'")

                if hasattr(model, 'inference_cross_lingual'):
                    synthesis_generator = model.inference_cross_lingual(
                        text, prompt_speech_16k, stream=stream, speed=speed
                    )
                else:
                    synthesis_generator = model.inference_zero_shot(
                        text, "", prompt_speech_16k, stream=stream, speed=speed
                    )
            else:
                raise VoiceNotFoundError(f"Cached voice '{voice_id}' not found")

            all_audio_data = []
            chunk_count = 0
            max_chunks = 200
            expected_duration = len(text) * 0.15 / speed
            max_samples = int(model.sample_rate * expected_duration * 5)

            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunk = model_output['tts_speech'].numpy().flatten()
                    all_audio_data.extend(audio_chunk)
                    chunk_count += 1

                    if chunk_count >= max_chunks or len(all_audio_data) > max_samples:
                        logger.warning(f"Stopping generation: limits reached")
                        break

            if not all_audio_data:
                raise SynthesisError("No audio generated")

            final_audio = torch.tensor(all_audio_data, dtype=torch.float32).unsqueeze(0)
            actual_duration = len(all_audio_data) / model.sample_rate
            logger.info(f"Final audio: {final_audio.shape}, chunks: {chunk_count}, duration: {actual_duration:.2f}s")

            torchaudio.save(output_path, final_audio.cpu(), model.sample_rate)
            return time.time() - start_time

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def synthesize_with_zero_shot(self, text: str, prompt_text: str,
                                        prompt_audio_path: str, output_path: str,
                                        speed: float = 1.0, stream: bool = False) -> float:
        """Zero-shot synthesis"""
        start_time = time.time()

        def _sync_synthesis():
            model = self.voice_manager._get_active_model()
            if not model:
                raise ModelNotReadyError("CosyVoice3 model not ready")

            prompt_speech_16k = postprocess(load_wav(prompt_audio_path, PROMPT_SR))
            set_all_random_seed(42)

            synthesis_generator = model.inference_zero_shot(
                text, prompt_text, prompt_speech_16k, stream=stream, speed=speed
            )

            audio_chunks = []
            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunks.append(model_output['tts_speech'])

            if not audio_chunks:
                raise SynthesisError("No audio generated")

            final_audio = torch.cat(audio_chunks, dim=1)
            torchaudio.save(output_path, final_audio, model.sample_rate)
            return time.time() - start_time

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def _resolve_audio_path(self, audio_url: str) -> str:
        """Resolve audio URL to local file path"""
        if os.path.exists(audio_url):
            return audio_url

        if audio_url.startswith('/api/v3/audio/'):
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
