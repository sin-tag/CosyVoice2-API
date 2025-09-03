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

from app.core.voice_manager import VoiceManager
from app.models.synthesis import (
    SFTSynthesisRequest, ZeroShotSynthesisRequest, 
    CrossLingualSynthesisRequest, InstructSynthesisRequest,
    SynthesisResponse, AudioFormat
)
from app.core.config import settings
from app.core.exceptions import SynthesisError, VoiceNotFoundError, ModelNotReadyError
from app.utils.file_utils import file_manager
from app.utils.audio import audio_processor

logger = logging.getLogger(__name__)


class SynthesisEngine:
    """Voice synthesis engine"""
    
    def __init__(self, voice_manager: VoiceManager):
        self.voice_manager = voice_manager
    
    async def synthesize_sft(self, request: SFTSynthesisRequest) -> SynthesisResponse:
        """Synthesize speech using pre-trained voice (SFT mode)"""
        try:
            model = self.voice_manager._get_active_model()
            if not model:
                raise ModelNotReadyError("CosyVoice model not ready")

            # Check if voice exists in pre-trained voices OR cached voices
            available_pretrained_voices = await self.voice_manager.get_available_pretrained_voices()
            cached_voice = await self.voice_manager.get_voice(request.voice_id)

            # Voice must exist either as pretrained or cached
            if request.voice_id not in available_pretrained_voices and not cached_voice:
                raise VoiceNotFoundError(f"Voice '{request.voice_id}' not found in pretrained or cached voices")

            # Generate unique output filename
            output_filename = f"sft_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)

            # Ensure output directory exists
            file_manager.ensure_directory_exists(os.path.dirname(output_path))

            # Perform synthesis
            if cached_voice:
                # Use cached voice synthesis
                synthesis_time = await self._synthesize_with_cached_voice(
                    model, request.text, request.voice_id,
                    output_path, request.speed, request.stream
                )
            else:
                # Use pretrained voice synthesis
                synthesis_time = await self._synthesize_with_model(
                    model, "sft", request.text, request.voice_id,
                    output_path, request.speed, request.stream
                )

            # Get audio duration
            duration = await self._get_audio_duration(output_path)

            return SynthesisResponse(
                success=True,
                message="Synthesis completed successfully",
                audio_url=f"/api/v1/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )

        except Exception as e:
            logger.error(f"Error in SFT synthesis: {e}")
            raise SynthesisError(f"SFT synthesis failed: {str(e)}")
    
    async def synthesize_zero_shot(self, request: ZeroShotSynthesisRequest, 
                                 prompt_audio: Optional[bytes] = None) -> SynthesisResponse:
        """Synthesize speech using zero-shot voice cloning"""
        try:
            model = self.voice_manager._get_active_model()
            if not model:
                raise ModelNotReadyError("CosyVoice model not ready")
            
            # Generate unique output filename
            output_filename = f"zero_shot_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)
            
            # Ensure output directory exists
            file_manager.ensure_directory_exists(os.path.dirname(output_path))
            
            # Handle voice source (cached voice or uploaded audio)
            if request.voice_id:
                # Use cached voice
                voice = await self.voice_manager.get_voice(request.voice_id)
                if not voice:
                    raise VoiceNotFoundError(f"Cached voice '{request.voice_id}' not found")
                
                synthesis_time = await self._synthesize_with_cached_voice(
                    model, request.text, request.voice_id, 
                    output_path, request.speed, request.stream
                )
            else:
                # Use uploaded audio
                if not prompt_audio or not request.prompt_text:
                    raise ValueError("prompt_audio and prompt_text are required when not using cached voice")
                
                synthesis_time = await self._synthesize_with_prompt_audio(
                    model, request.text, request.prompt_text, prompt_audio,
                    output_path, request.speed, request.stream
                )
            
            # Get audio duration
            duration = await self._get_audio_duration(output_path)
            
            return SynthesisResponse(
                success=True,
                message="Zero-shot synthesis completed successfully",
                audio_url=f"/api/v1/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )
            
        except Exception as e:
            logger.error(f"Error in zero-shot synthesis: {e}")
            raise SynthesisError(f"Zero-shot synthesis failed: {str(e)}")
    
    async def synthesize_cross_lingual(self, request: CrossLingualSynthesisRequest,
                                     prompt_audio: Optional[bytes] = None) -> SynthesisResponse:
        """Synthesize speech using cross-lingual voice cloning"""
        try:
            model = self.voice_manager._get_active_model()
            if not model:
                raise ModelNotReadyError("CosyVoice model not ready")
            
            # Check if model supports cross-lingual
            if hasattr(model, 'instruct') and model.instruct:
                raise ValueError("Cross-lingual mode not supported with instruct model")
            
            # Generate unique output filename
            output_filename = f"cross_lingual_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)
            
            # Ensure output directory exists
            file_manager.ensure_directory_exists(os.path.dirname(output_path))
            
            # Handle voice source (cached voice or uploaded audio)
            if request.voice_id:
                # Use cached voice
                voice = await self.voice_manager.get_voice(request.voice_id)
                if not voice:
                    raise VoiceNotFoundError(f"Cached voice '{request.voice_id}' not found")
                
                synthesis_time = await self._synthesize_cross_lingual_cached(
                    model, request.text, request.voice_id,
                    output_path, request.speed, request.stream
                )
            else:
                # Use uploaded audio
                if not prompt_audio:
                    raise ValueError("prompt_audio is required when not using cached voice")
                
                synthesis_time = await self._synthesize_cross_lingual_prompt(
                    model, request.text, prompt_audio,
                    output_path, request.speed, request.stream
                )
            
            # Get audio duration
            duration = await self._get_audio_duration(output_path)
            
            return SynthesisResponse(
                success=True,
                message="Cross-lingual synthesis completed successfully",
                audio_url=f"/api/v1/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )
            
        except Exception as e:
            logger.error(f"Error in cross-lingual synthesis: {e}")
            raise SynthesisError(f"Cross-lingual synthesis failed: {str(e)}")
    
    async def synthesize_instruct(self, request: InstructSynthesisRequest) -> SynthesisResponse:
        """Synthesize speech using natural language control (instruct mode)"""
        try:
            model = self.voice_manager._get_active_model()
            if not model:
                raise ModelNotReadyError("CosyVoice model not ready")
            
            # Check if model supports instruct mode
            if not hasattr(model, 'instruct') or not model.instruct:
                raise ValueError("Instruct mode not supported with this model")
            
            # Check if voice exists in pre-trained voices
            available_voices = await self.voice_manager.get_available_pretrained_voices()
            if request.voice_id not in available_voices:
                raise VoiceNotFoundError(f"Pre-trained voice '{request.voice_id}' not found")
            
            # Generate unique output filename
            output_filename = f"instruct_{uuid.uuid4().hex[:8]}.{request.format.value}"
            output_path = file_manager.get_output_audio_path(output_filename)
            
            # Ensure output directory exists
            file_manager.ensure_directory_exists(os.path.dirname(output_path))
            
            # Perform instruct synthesis
            synthesis_time = await self._synthesize_instruct_mode(
                model, request.text, request.voice_id, request.instruct_text,
                output_path, request.speed, request.stream
            )
            
            # Get audio duration
            duration = await self._get_audio_duration(output_path)
            
            return SynthesisResponse(
                success=True,
                message="Instruct synthesis completed successfully",
                audio_url=f"/api/v1/audio/{output_filename}",
                file_path=output_path,
                duration=duration,
                format=request.format,
                synthesis_time=synthesis_time
            )
            
        except Exception as e:
            logger.error(f"Error in instruct synthesis: {e}")
            raise SynthesisError(f"Instruct synthesis failed: {str(e)}")
    
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

    async def _synthesize_with_cached_voice(self, model, text: str, voice_id: str,
                                          output_path: str, speed: float, stream: bool) -> float:
        """Synthesize with cached voice"""
        import time
        start_time = time.time()

        loop = asyncio.get_event_loop()

        # Use zero-shot inference with cached voice
        synthesis_generator = await loop.run_in_executor(
            None, lambda: model.inference_zero_shot(
                text, "", None, zero_shot_spk_id=voice_id, stream=stream, speed=speed
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
