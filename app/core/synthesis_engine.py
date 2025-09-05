"""
Synthesis engine for CosyVoice2 API
Handles voice synthesis operations
"""

import os
import asyncio
import logging
import tempfile
import uuid
from typing import Optional, Generator, Any, Dict
from pathlib import Path

import torch
import torchaudio
import soundfile as sf
import librosa
from cosyvoice.utils.file_utils import load_wav
from cosyvoice.utils.common import set_all_random_seed

from app.core.voice_manager import VoiceManager
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

def detect_language_and_add_tags(text: str) -> str:
    """
    Detect language and add appropriate tags for CosyVoice cross-lingual synthesis
    """
    import re

    # Check for Chinese characters
    if re.search(r'[\u4e00-\u9fff]', text):
        return f"<|zh|>{text}"

    # Check for Japanese characters (hiragana, katakana, kanji)
    elif re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
        return f"<|jp|>{text}"

    # Check for Korean characters
    elif re.search(r'[\uac00-\ud7af]', text):
        return f"<|ko|>{text}"

    # Check for Cantonese (basic detection)
    elif any(word in text for word in ['係', '喺', '咗', '嘅', '佢', '唔']):
        return f"<|yue|>{text}"

    # Default to English for Latin characters
    else:
        return f"<|en|>{text}"

def postprocess(speech, top_db=60, hop_length=220, win_length=440):
    """Postprocess audio like in the original CosyVoice webui"""
    speech, _ = librosa.effects.trim(
        speech, top_db=top_db,
        frame_length=win_length,
        hop_length=hop_length
    )
    if speech.abs().max() > MAX_VAL:
        speech = speech / speech.abs().max() * MAX_VAL
    # Add silence at the end
    silence_duration = int(22050 * 0.2)  # Assume 22050 sample rate for now
    speech = torch.concat([speech, torch.zeros(1, silence_duration)], dim=1)
    return speech


class SynthesisEngine:
    """Voice synthesis engine"""
    
    def __init__(self, voice_manager: VoiceManager):
        self.voice_manager = voice_manager
    
    async def synthesize_cross_lingual_with_audio(self, request: CrossLingualWithAudioRequest) -> SynthesisResponse:
        """跨语种复刻 - 带音频文件 (Cross-lingual voice cloning with audio file)"""
        try:
            model = self.voice_manager._get_active_model()
            if not model:
                raise ModelNotReadyError("CosyVoice model not ready")

            # Load prompt audio
            prompt_audio_path = await self._resolve_audio_path(request.prompt_audio_url)
            if not os.path.exists(prompt_audio_path):
                raise FileNotFoundError(f"Prompt audio file not found: {prompt_audio_path}")

            # Generate unique output filename
            output_filename = f"cross_lingual_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)

            # Ensure output directory exists
            file_manager.ensure_directory_exists(os.path.dirname(output_path))

            # Perform synthesis
            if request.instruct_text:
                # Use instruct mode for fine-grained control
                synthesis_time = await self._synthesize_with_instruct(
                    model, request.text, request.prompt_text, prompt_audio_path,
                    request.instruct_text, output_path, request.speed, request.stream
                )
            else:
                # Use zero-shot mode
                synthesis_time = await self._synthesize_with_zero_shot(
                    model, request.text, request.prompt_text, prompt_audio_path,
                    output_path, request.speed, request.stream
                )

            # Get audio duration
            duration = await self._get_audio_duration(output_path)

            return SynthesisResponse(
                success=True,
                message="跨语种复刻合成完成 (Cross-lingual synthesis completed)",
                audio_url=f"/api/v1/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )

        except Exception as e:
            logger.error(f"Error in cross-lingual synthesis with audio: {e}")
            raise SynthesisError(f"Cross-lingual synthesis failed: {str(e)}")

    async def synthesize_cross_lingual_with_cache(self, request: CrossLingualWithCacheRequest) -> SynthesisResponse:
        """跨语种复刻 - 使用缓存语音 (Cross-lingual voice cloning with cached voice)"""
        try:
            model = self.voice_manager._get_active_model()
            if not model:
                raise ModelNotReadyError("CosyVoice model not ready")

            # Check if cached voice exists
            cached_voice = await self.voice_manager.get_voice(request.voice_id)
            if not cached_voice:
                raise VoiceNotFoundError(f"Cached voice '{request.voice_id}' not found")

            # Generate unique output filename
            output_filename = f"cross_lingual_cache_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)

            # Ensure output directory exists
            file_manager.ensure_directory_exists(os.path.dirname(output_path))

            # Perform synthesis
            if request.instruct_text:
                # Use instruct mode with cached voice
                synthesis_time = await self._synthesize_with_cached_voice_instruct(
                    model, request.text, request.voice_id, request.instruct_text,
                    output_path, request.speed, request.stream
                )
            else:
                # Use cached voice directly
                synthesis_time = await self._synthesize_with_cached_voice(
                    model, request.text, request.voice_id,
                    output_path, request.speed, request.stream, request.prompt_text
                )

            # Get audio duration
            duration = await self._get_audio_duration(output_path)

            return SynthesisResponse(
                success=True,
                message="跨语种复刻合成完成 (Cross-lingual synthesis completed)",
                audio_url=f"/api/v1/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )

        except Exception as e:
            logger.error(f"Error in cross-lingual synthesis with cache: {e}")
            raise SynthesisError(f"Cross-lingual synthesis failed: {str(e)}")
    

    

    

    
    async def _synthesize_with_model(self, model, mode: str, text: str, voice_id: str,
                                   output_path: str, speed: float, stream: bool) -> float:
        """Common synthesis method"""
        import time
        start_time = time.time()

        def _sync_synthesis():
            if mode == "sft":
                # SFT synthesis
                synthesis_generator = model.inference_sft(text, voice_id, stream=stream, speed=speed)
            else:
                raise ValueError(f"Unsupported synthesis mode: {mode}")

            # Collect audio chunks
            audio_chunks = []
            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunks.append(model_output['tts_speech'])

            if not audio_chunks:
                raise SynthesisError("No audio generated")

            # Concatenate audio chunks
            final_audio = torch.cat(audio_chunks, dim=1)

            # Save audio
            torchaudio.save(output_path, final_audio, model.sample_rate)

            return time.time() - start_time

        # Run synthesis in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def _synthesize_with_zero_shot(self, model, text: str, prompt_text: str,
                                       prompt_audio_path: str, output_path: str,
                                       speed: float, stream: bool) -> float:
        """Zero-shot synthesis with prompt audio"""
        import time
        start_time = time.time()

        def _sync_synthesis():
            # Load and postprocess prompt audio like in original webui
            prompt_speech_16k = postprocess(load_wav(prompt_audio_path, PROMPT_SR))

            # Set random seed for reproducible results
            set_all_random_seed(42)

            # Add language tags for better cross-lingual support
            tagged_text = detect_language_and_add_tags(text)

            # Use zero-shot inference with language tags
            synthesis_generator = model.inference_zero_shot(
                tagged_text, prompt_text, prompt_speech_16k, stream=stream, speed=speed
            )

            # Collect audio chunks
            audio_chunks = []
            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunks.append(model_output['tts_speech'])

            if not audio_chunks:
                raise SynthesisError("No audio generated")

            # Concatenate audio chunks
            final_audio = torch.cat(audio_chunks, dim=1)

            # Save audio
            torchaudio.save(output_path, final_audio, model.sample_rate)

            return time.time() - start_time

        # Run synthesis in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def _synthesize_with_instruct(self, model, text: str, prompt_text: str,
                                      prompt_audio_path: str, instruct_text: str,
                                      output_path: str, speed: float, stream: bool) -> float:
        """Instruct synthesis with prompt audio"""
        import time
        start_time = time.time()

        def _sync_synthesis():
            # Load and postprocess prompt audio like in original webui
            prompt_speech_16k = postprocess(load_wav(prompt_audio_path, PROMPT_SR))

            # Set random seed for reproducible results
            set_all_random_seed(42)

            # Add language tags to text for better cross-lingual support
            tagged_text = detect_language_and_add_tags(text)

            # For cross-lingual with instruct, prioritize cross-lingual mode over instruct
            # This prevents the "tùng tùng" issue when using instruct with different languages
            if hasattr(model, 'inference_cross_lingual'):
                # Use cross-lingual mode for better language handling
                # Note: cross-lingual doesn't use prompt_text, only prompt_audio
                logger.info(f"Using cross-lingual mode for text: {tagged_text}")
                synthesis_generator = model.inference_cross_lingual(
                    tagged_text, prompt_speech_16k, stream=stream, speed=speed
                )
            elif hasattr(model, 'inference_instruct2') and instruct_text:
                # CosyVoice2 with instruct2 - use with language tags
                logger.info(f"Using instruct2 mode with language tags")
                synthesis_generator = model.inference_instruct2(
                    tagged_text, instruct_text, prompt_speech_16k, stream=stream, speed=speed
                )
            else:
                # Fallback to zero-shot with language tags
                # Combine prompt_text and instruct_text for better context
                combined_prompt = f"{prompt_text}. {instruct_text}" if prompt_text else instruct_text
                logger.info(f"Using zero-shot mode with combined prompt")
                synthesis_generator = model.inference_zero_shot(
                    tagged_text, combined_prompt, prompt_speech_16k, stream=stream, speed=speed
                )

            # Collect audio chunks
            audio_chunks = []
            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunks.append(model_output['tts_speech'])

            if not audio_chunks:
                raise SynthesisError("No audio generated")

            # Concatenate audio chunks
            final_audio = torch.cat(audio_chunks, dim=1)

            # Save audio
            torchaudio.save(output_path, final_audio, model.sample_rate)

            return time.time() - start_time

        # Run synthesis in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def _synthesize_with_cached_voice_instruct(self, model, text: str, voice_id: str,
                                                   instruct_text: str, output_path: str,
                                                   speed: float, stream: bool) -> float:
        """Instruct synthesis with cached voice"""
        import time
        start_time = time.time()

        def _sync_synthesis():
            # Get cached voice audio path
            voice = self.voice_manager.voice_cache.voices.get(voice_id)
            if not voice or not voice.audio_file_path:
                raise VoiceNotFoundError(f"Cached voice '{voice_id}' audio not found")

            # Load and postprocess cached voice audio
            prompt_speech_16k = postprocess(load_wav(voice.audio_file_path, PROMPT_SR))

            # Set random seed for reproducible results
            set_all_random_seed(42)

            # Use instruct inference with cached voice
            if hasattr(model, 'instruct') and model.instruct:
                synthesis_generator = model.inference_instruct(
                    text, voice_id, instruct_text, stream=stream, speed=speed
                )
            else:
                # Fallback to zero-shot with instruct as prompt text
                synthesis_generator = model.inference_zero_shot(
                    text, instruct_text, prompt_speech_16k, stream=stream, speed=speed
                )

            # Collect audio chunks
            audio_chunks = []
            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunks.append(model_output['tts_speech'])

            if not audio_chunks:
                raise SynthesisError("No audio generated")

            # Concatenate audio chunks
            final_audio = torch.cat(audio_chunks, dim=1)

            # Save audio
            torchaudio.save(output_path, final_audio, model.sample_rate)

            return time.time() - start_time

        # Run synthesis in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def _resolve_audio_path(self, audio_url: str) -> str:
        """Resolve audio URL to local file path"""
        # If it's already a local path, return as is
        if os.path.exists(audio_url):
            return audio_url

        # If it's a URL starting with /api/v1/audio/, resolve to local path
        if audio_url.startswith('/api/v1/audio/'):
            filename = audio_url.split('/')[-1]
            return file_manager.get_output_audio_path(filename)

        # If it's a relative path, make it absolute
        if not os.path.isabs(audio_url):
            return os.path.abspath(audio_url)

        return audio_url

    async def _synthesize_with_cached_voice(self, model, text: str, voice_id: str,
                                          output_path: str, speed: float, stream: bool, prompt_text: str = None) -> float:
        """Synthesize with cached voice using SFT method"""
        import time
        start_time = time.time()

        def _sync_synthesis():
            # Set random seed for reproducible results
            set_all_random_seed(42)

            # Check if voice is in spk2info (loaded cached voices)
            if hasattr(model, 'frontend') and voice_id in model.frontend.spk2info:
                # Use SFT synthesis with cached voice (no text_frontend parameter)
                synthesis_generator = model.inference_sft(text, voice_id, stream=stream, speed=speed)
            else:
                # Get cached voice audio for zero-shot
                voice = self.voice_manager.voice_cache.voices.get(voice_id)
                if voice and voice.audio_file_path:
                    prompt_speech_16k = postprocess(load_wav(voice.audio_file_path, PROMPT_SR))
                    # Use provided prompt_text or fallback to cached voice prompt_text
                    used_prompt_text = prompt_text if prompt_text else (voice.prompt_text or "")
                    synthesis_generator = model.inference_zero_shot(
                        text, used_prompt_text, prompt_speech_16k, stream=stream, speed=speed
                    )
                else:
                    raise VoiceNotFoundError(f"Cached voice '{voice_id}' not found")

            # Collect audio chunks
            audio_chunks = []
            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunks.append(model_output['tts_speech'])

            if not audio_chunks:
                raise SynthesisError("No audio generated")

            # Concatenate audio chunks
            final_audio = torch.cat(audio_chunks, dim=1)

            # Save audio
            torchaudio.save(output_path, final_audio, model.sample_rate)

            return time.time() - start_time

        # Run synthesis in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

    async def _synthesize_with_prompt_audio(self, model, text: str, prompt_text: str,
                                          prompt_audio: bytes, output_path: str,
                                          speed: float, stream: bool) -> float:
        """Synthesize with prompt audio"""
        import time
        start_time = time.time()

        # Save prompt audio to temp file
        temp_audio_path = await file_manager.save_temp_file(prompt_audio, "prompt.wav")

        try:
            # Load prompt audio
            from cosyvoice.utils.file_utils import load_wav
            loop = asyncio.get_event_loop()
            prompt_speech_16k = await loop.run_in_executor(
                None, load_wav, temp_audio_path, 16000
            )

            # Perform zero-shot synthesis
            synthesis_generator = await loop.run_in_executor(
                None, lambda: model.inference_zero_shot(
                    text, prompt_text, prompt_speech_16k, stream=stream, speed=speed
                )
            )

            # Collect and save audio
            audio_chunks = []
            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunks.append(model_output['tts_speech'])

            if not audio_chunks:
                raise SynthesisError("No audio generated")

            final_audio = torch.cat(audio_chunks, dim=1)
            torchaudio.save(output_path, final_audio, model.sample_rate)

            return time.time() - start_time

        finally:
            # Clean up temp file
            file_manager.delete_file(temp_audio_path)

    async def _synthesize_cross_lingual_cached(self, model, text: str, voice_id: str,
                                             output_path: str, speed: float, stream: bool) -> float:
        """Cross-lingual synthesis with cached voice"""
        return await self._synthesize_with_cached_voice(model, text, voice_id, output_path, speed, stream)

    async def _synthesize_cross_lingual_prompt(self, model, text: str, prompt_audio: bytes,
                                             output_path: str, speed: float, stream: bool) -> float:
        """Cross-lingual synthesis with prompt audio"""
        import time
        start_time = time.time()

        # Save prompt audio to temp file
        temp_audio_path = await file_manager.save_temp_file(prompt_audio, "prompt.wav")

        try:
            # Load prompt audio
            from cosyvoice.utils.file_utils import load_wav
            loop = asyncio.get_event_loop()
            prompt_speech_16k = await loop.run_in_executor(
                None, load_wav, temp_audio_path, 16000
            )

            # Perform cross-lingual synthesis (no prompt text needed)
            synthesis_generator = await loop.run_in_executor(
                None, lambda: model.inference_zero_shot(
                    text, "", prompt_speech_16k, stream=stream, speed=speed
                )
            )

            # Collect and save audio
            audio_chunks = []
            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    audio_chunks.append(model_output['tts_speech'])

            if not audio_chunks:
                raise SynthesisError("No audio generated")

            final_audio = torch.cat(audio_chunks, dim=1)
            torchaudio.save(output_path, final_audio, model.sample_rate)

            return time.time() - start_time

        finally:
            # Clean up temp file
            file_manager.delete_file(temp_audio_path)

    async def _synthesize_instruct_mode(self, model, text: str, voice_id: str,
                                      instruct_text: str, output_path: str,
                                      speed: float, stream: bool) -> float:
        """Instruct mode synthesis"""
        import time
        start_time = time.time()

        loop = asyncio.get_event_loop()

        # Perform instruct synthesis
        synthesis_generator = await loop.run_in_executor(
            None, lambda: model.inference_instruct(
                text, voice_id, instruct_text, stream=stream, speed=speed
            )
        )

        # Collect and save audio
        audio_chunks = []
        for model_output in synthesis_generator:
            if 'tts_speech' in model_output:
                audio_chunks.append(model_output['tts_speech'])

        if not audio_chunks:
            raise SynthesisError("No audio generated")

        final_audio = torch.cat(audio_chunks, dim=1)
        torchaudio.save(output_path, final_audio, model.sample_rate)

        return time.time() - start_time

    async def _get_audio_duration(self, audio_path: str) -> Optional[float]:
        """Get audio file duration"""
        try:
            audio_info = await audio_processor._get_audio_info(audio_path)
            return audio_info[0] if audio_info else None
        except Exception:
            return None
