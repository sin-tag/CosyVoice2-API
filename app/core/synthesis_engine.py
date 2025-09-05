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
    DISABLED - Cross-lingual synthesis không cần language tags
    Repo gốc CosyVoice không sử dụng language tags cho inference_cross_lingual
    Model tự detect language từ text và audio
    """
    # Return original text - repo gốc không sử dụng language tags
    return text

def postprocess(speech, sample_rate, top_db=60, hop_length=220, win_length=440):
    """Postprocess audio EXACTLY like in the original CosyVoice webui"""
    speech, _ = librosa.effects.trim(
        speech, top_db=top_db,
        frame_length=win_length,
        hop_length=hop_length
    )
    if speech.abs().max() > MAX_VAL:
        speech = speech / speech.abs().max() * MAX_VAL
    # Add silence at the end - EXACT như webui.py gốc
    speech = torch.concat([speech, torch.zeros(1, int(sample_rate * 0.2))], dim=1)
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

            # Perform synthesis - chỉ sử dụng cross-lingual mode như repo gốc
            # KHÔNG sử dụng instruct_text hay prompt_text
            synthesis_time = await self._synthesize_cross_lingual_cached(
                model, request.text, request.voice_id,
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
            prompt_speech_16k = postprocess(load_wav(prompt_audio_path, PROMPT_SR), model.sample_rate)

            # Set random seed for reproducible results
            set_all_random_seed(42)

            # Repo gốc CosyVoice: inference_cross_lingual chỉ cần text (không cần language tags)
            # Model tự detect language từ text content

            if hasattr(model, 'inference_cross_lingual'):
                # EXACT match với repo gốc: inference_cross_lingual(tts_text, prompt_speech_16k, stream, speed)
                logger.info(f"Using cross-lingual mode (exact match với repo gốc): text='{text}'")
                if instruct_text:
                    logger.info(f"Note: instruct_text ignored in cross-lingual mode (như repo gốc): '{instruct_text[:50]}...'")
                if prompt_text:
                    logger.info(f"Note: prompt_text ignored in cross-lingual mode (như repo gốc): '{prompt_text[:50]}...'")

                # EXACT signature như repo gốc: inference_cross_lingual(tts_text, prompt_speech_16k, stream, speed)
                synthesis_generator = model.inference_cross_lingual(
                    text, prompt_speech_16k, stream=stream, speed=speed
                )
            else:
                # Fallback to zero-shot if cross_lingual not available
                logger.info(f"Cross-lingual not available, using zero-shot fallback: text='{text}'")
                synthesis_generator = model.inference_zero_shot(
                    text, "", prompt_speech_16k, stream=stream, speed=speed
                )

            # Process audio chunks EXACTLY like webui.py gốc - NO CONCATENATION!
            # Webui.py yields each chunk separately, we collect them properly
            all_audio_data = []
            chunk_count = 0

            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    # EXACT như webui.py: flatten audio chunk
                    audio_chunk = model_output['tts_speech'].numpy().flatten()
                    all_audio_data.extend(audio_chunk)  # Extend, not append!
                    chunk_count += 1
                    logger.info(f"📊 Processed chunk {chunk_count}: {len(audio_chunk)} samples")

            if not all_audio_data:
                raise SynthesisError("No audio generated")

            # Convert to tensor - EXACT như webui.py output
            final_audio = torch.tensor(all_audio_data, dtype=torch.float32).unsqueeze(0)
            logger.info(f"✅ Final audio shape: {final_audio.shape}, chunks: {chunk_count}")

            # Save audio to file - EXACT sample rate như webui.py
            torchaudio.save(output_path, final_audio.cpu(), model.sample_rate)

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
        """Cross-lingual synthesis with cached voice - sử dụng inference_cross_lingual như repo gốc"""
        import time
        start_time = time.time()

        def _sync_synthesis():
            # Set random seed for reproducible results
            set_all_random_seed(42)

            # Get cached voice - ALWAYS use cross-lingual (跨语种复刻) as requested
            voice = self.voice_manager.voice_cache.voices.get(voice_id)
            if voice and voice.audio_file_path:
                prompt_speech_16k = postprocess(load_wav(voice.audio_file_path, PROMPT_SR), model.sample_rate)

                # ALWAYS use cross-lingual method as requested - no exceptions
                logger.info(f"🎯 USING CROSS-LINGUAL MODE (跨语种复刻) for voice '{voice_id}': text='{text}'")

                # Check for Japanese and add special handling to prevent hallucination
                import re
                is_japanese = bool(re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text))

                if is_japanese:
                    logger.info(f"🇯🇵 Japanese detected - applying anti-hallucination measures")
                    # For Japanese, we might need to limit generation or add special parameters
                    # But still use cross-lingual as requested

                if hasattr(model, 'inference_cross_lingual'):
                    logger.info(f"🔧 Method: model.inference_cross_lingual(text='{text}', prompt_speech_16k, stream={stream}, speed={speed})")
                    synthesis_generator = model.inference_cross_lingual(
                        text, prompt_speech_16k, stream=stream, speed=speed
                    )
                    logger.info(f"✅ Cross-lingual synthesis generator created successfully")
                else:
                    # Fallback to zero-shot if cross_lingual not available
                    logger.info(f"❌ Cross-lingual not available, using zero-shot fallback for cached voice '{voice_id}'")
                    synthesis_generator = model.inference_zero_shot(
                        text, "", prompt_speech_16k, stream=stream, speed=speed
                    )
            else:
                raise VoiceNotFoundError(f"Cached voice '{voice_id}' not found")

            # Process audio chunks with anti-hallucination for Japanese
            all_audio_data = []
            chunk_count = 0
            max_chunks = 100 if is_japanese else 200  # Increase Japanese limit
            expected_duration = len(text) * 0.15 / speed  # CRITICAL FIX: Adjust for speed!
            max_samples = int(model.sample_rate * expected_duration * 5)  # Max 5x expected duration (increased)

            logger.debug(f"🎯 Generation limits: max_chunks={max_chunks}, max_samples={max_samples}")

            for model_output in synthesis_generator:
                if 'tts_speech' in model_output:
                    # EXACT như webui.py: flatten audio chunk
                    audio_chunk = model_output['tts_speech'].numpy().flatten()

                    # ADD CHUNK FIRST, then check limits
                    all_audio_data.extend(audio_chunk)  # Extend, not append!
                    chunk_count += 1
                    logger.debug(f"📊 Processed chunk {chunk_count}: {len(audio_chunk)} samples, total: {len(all_audio_data)}")

                    # Anti-hallucination: Stop AFTER adding chunk if limits reached
                    if chunk_count >= max_chunks:
                        logger.warning(f"🛑 Stopping generation: reached max chunks ({max_chunks}) - but keeping current audio")
                        break

                    if len(all_audio_data) > max_samples:
                        logger.warning(f"🛑 Stopping generation: exceeded max samples ({max_samples}) - but keeping current audio")
                        break

            if not all_audio_data:
                raise SynthesisError("No audio generated")

            # Convert to tensor - EXACT như webui.py output
            final_audio = torch.tensor(all_audio_data, dtype=torch.float32).unsqueeze(0)
            actual_duration = len(all_audio_data) / model.sample_rate
            logger.info(f"✅ Final audio: {final_audio.shape}, chunks: {chunk_count}, duration: {actual_duration:.2f}s")

            # Save audio to file - EXACT sample rate như webui.py
            torchaudio.save(output_path, final_audio.cpu(), model.sample_rate)

            return time.time() - start_time

        # Run synthesis in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_synthesis)

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
