"""
Synthesis engine for Chatterbox TTS API
Handles voice synthesis operations with Chatterbox specific features
"""

import os
import asyncio
import logging
import uuid
import time
import re
from typing import Optional, Generator, Any, Dict, List

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
MAX_CHUNK_LENGTH = 500  # Maximum characters per chunk for stable synthesis

# NOTE: Thread safety is handled by AsyncTaskManager queue - tasks are processed sequentially


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


def split_text_into_chunks(text: str, max_length: int = MAX_CHUNK_LENGTH) -> List[str]:
    """
    Split long text into smaller chunks at natural boundaries.

    Splits at sentence boundaries (., !, ?, ;) first, then at commas,
    and finally at word boundaries if needed.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text.strip()

    # Sentence-ending patterns (prioritized)
    sentence_pattern = re.compile(r'([.!?;])\s+')
    comma_pattern = re.compile(r'(,)\s+')

    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break

        # Try to find a sentence boundary within max_length
        chunk_text = remaining[:max_length]

        # Look for last sentence boundary
        matches = list(sentence_pattern.finditer(chunk_text))
        if matches:
            # Use the last sentence boundary
            last_match = matches[-1]
            split_pos = last_match.end()
            chunks.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()
            continue

        # Try comma boundaries
        matches = list(comma_pattern.finditer(chunk_text))
        if matches:
            last_match = matches[-1]
            split_pos = last_match.end()
            chunks.append(remaining[:split_pos].strip())
            remaining = remaining[split_pos:].strip()
            continue

        # Fall back to word boundary
        last_space = chunk_text.rfind(' ')
        if last_space > max_length // 2:
            chunks.append(remaining[:last_space].strip())
            remaining = remaining[last_space:].strip()
        else:
            # Force split if no good boundary found
            chunks.append(remaining[:max_length].strip())
            remaining = remaining[max_length:].strip()

    return [c for c in chunks if c]  # Remove empty chunks


def concatenate_audio_tensors(audio_list: List[torch.Tensor], sample_rate: int = 24000) -> torch.Tensor:
    """
    Concatenate multiple audio tensors with small silence gaps.
    Filters out None values and invalid tensors.
    """
    # Filter out None and invalid tensors
    valid_audio = []
    for i, audio in enumerate(audio_list):
        if audio is None:
            logger.warning(f"Chunk {i} returned None, skipping")
            continue
        if not isinstance(audio, torch.Tensor):
            logger.warning(f"Chunk {i} is not a tensor ({type(audio)}), skipping")
            continue
        if audio.numel() == 0:
            logger.warning(f"Chunk {i} is empty tensor, skipping")
            continue
        valid_audio.append(audio)

    if not valid_audio:
        raise ValueError("No valid audio tensors to concatenate - all chunks failed")

    if len(valid_audio) == 1:
        return valid_audio[0]

    # Small silence gap between chunks (50ms)
    gap_samples = int(sample_rate * 0.05)
    silence_gap = torch.zeros(1, gap_samples)

    # Normalize all tensors to same shape (1, samples)
    normalized = []
    for audio in valid_audio:
        if audio.dim() == 1:
            audio = audio.unsqueeze(0)
        normalized.append(audio)

    # Concatenate with gaps
    result_parts = []
    for i, audio in enumerate(normalized):
        result_parts.append(audio)
        if i < len(normalized) - 1:
            result_parts.append(silence_gap)

    return torch.cat(result_parts, dim=1)


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

            # Support both voice_id and voice name
            cached_voice = await self.voice_manager.get_voice_by_id_or_name(request.voice_id)
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
        """Core synthesis with reference audio - supports long text via chunking"""
        start_time = time.time()
        model_type = self.voice_manager.model_type

        # Split long text into chunks
        chunks = split_text_into_chunks(text, MAX_CHUNK_LENGTH)
        total_chunks = len(chunks)

        if total_chunks > 1:
            logger.info(f"Long text detected ({len(text)} chars), split into {total_chunks} chunks")

        def _sync_synthesis():
            import torchaudio as ta

            logger.info(f"Starting synthesis: model_type={model_type}, lang={language}, text_len={len(text)}, chunks={total_chunks}")

            try:
                audio_chunks = []
                failed_chunks = []

                for i, chunk in enumerate(chunks):
                    if total_chunks > 1:
                        logger.info(f"Processing chunk {i+1}/{total_chunks} ({len(chunk)} chars)")

                    try:
                        if model_type == "multilingual":
                            wav = model.generate(
                                chunk,
                                language_id=language,
                                audio_prompt_path=prompt_audio_path
                            )
                        else:
                            wav = model.generate(
                                chunk,
                                audio_prompt_path=prompt_audio_path,
                                exaggeration=exaggeration,
                                cfg_weight=cfg_weight
                            )

                        # Validate output
                        if wav is None:
                            logger.warning(f"Chunk {i+1} returned None")
                            failed_chunks.append(i+1)
                        else:
                            audio_chunks.append(wav)

                    except Exception as chunk_error:
                        logger.error(f"Chunk {i+1} failed: {chunk_error}")
                        failed_chunks.append(i+1)
                        # Continue with other chunks instead of failing completely
                        continue

                if not audio_chunks:
                    raise SynthesisError(f"All {total_chunks} chunks failed to generate audio")

                if failed_chunks:
                    logger.warning(f"Some chunks failed: {failed_chunks}. Continuing with {len(audio_chunks)} successful chunks.")

                # Concatenate all chunks
                if len(audio_chunks) > 1:
                    final_wav = concatenate_audio_tensors(audio_chunks, model.sr)
                    logger.info(f"Concatenated {len(audio_chunks)} audio chunks")
                else:
                    final_wav = audio_chunks[0]

                # Validate final output
                if final_wav is None or not isinstance(final_wav, torch.Tensor):
                    raise SynthesisError("Failed to generate valid audio output")

                # Save using model's sample rate
                ta.save(output_path, final_wav, model.sr)
                logger.info(f"Saved synthesis output to: {output_path}")

                return time.time() - start_time

            except RuntimeError as e:
                error_msg = str(e)
                if "CUDA" in error_msg or "device-side assert" in error_msg:
                    logger.error(f"CUDA error during synthesis: {error_msg}")
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                    raise SynthesisError(f"CUDA error: {error_msg}. Try restarting the server.")
                raise

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
        Supports long text via automatic chunking.

        Args:
            text: Text to synthesize (supports up to 50000+ chars via chunking)
            prompt_audio_path: Path to reference audio (optional for multilingual)
            output_path: Path to save output
            language: Target language code (e.g., "en", "zh", "ja", "ko", etc.)
            exaggeration: Voice exaggeration factor
        """
        # Validate language code
        supported_languages = self.voice_manager.get_language_codes()
        if language not in supported_languages:
            logger.warning(f"Language '{language}' may not be supported. Supported: {supported_languages}")

        # Split long text into chunks
        chunks = split_text_into_chunks(text, MAX_CHUNK_LENGTH)
        total_chunks = len(chunks)

        if total_chunks > 1:
            logger.info(f"Long text detected ({len(text)} chars), split into {total_chunks} chunks")

        start_time = time.time()

        def _sync_synthesis():
            import torchaudio as ta

            model = self.voice_manager._get_active_model()
            if self.voice_manager.model_type != "multilingual":
                raise ValueError("Multilingual synthesis requires ChatterboxMultilingual model")

            logger.info(f"Starting multilingual synthesis: lang={language}, text_len={len(text)}, chunks={total_chunks}, audio={prompt_audio_path}")

            try:
                audio_chunks = []
                failed_chunks = []
                has_audio_prompt = prompt_audio_path and os.path.exists(prompt_audio_path)

                for i, chunk in enumerate(chunks):
                    if total_chunks > 1:
                        logger.info(f"Processing chunk {i+1}/{total_chunks} ({len(chunk)} chars)")

                    try:
                        if has_audio_prompt:
                            wav = model.generate(
                                chunk,
                                language_id=language,
                                audio_prompt_path=prompt_audio_path
                            )
                        else:
                            wav = model.generate(
                                chunk,
                                language_id=language
                            )

                        # Validate output
                        if wav is None:
                            logger.warning(f"Chunk {i+1} returned None")
                            failed_chunks.append(i+1)
                        else:
                            audio_chunks.append(wav)

                    except Exception as chunk_error:
                        logger.error(f"Chunk {i+1} failed: {chunk_error}")
                        failed_chunks.append(i+1)
                        continue

                if not audio_chunks:
                    raise SynthesisError(f"All {total_chunks} chunks failed to generate audio")

                if failed_chunks:
                    logger.warning(f"Some chunks failed: {failed_chunks}. Continuing with {len(audio_chunks)} successful chunks.")

                # Concatenate all chunks
                if len(audio_chunks) > 1:
                    final_wav = concatenate_audio_tensors(audio_chunks, model.sr)
                    logger.info(f"Concatenated {len(audio_chunks)} audio chunks")
                else:
                    final_wav = audio_chunks[0]

                # Validate final output
                if final_wav is None or not isinstance(final_wav, torch.Tensor):
                    raise SynthesisError("Failed to generate valid audio output")

                # Save using model's sample rate
                ta.save(output_path, final_wav, model.sr)
                logger.info(f"Saved output to: {output_path}")

                return time.time() - start_time

            except RuntimeError as e:
                error_msg = str(e)
                if "CUDA" in error_msg or "device-side assert" in error_msg:
                    logger.error(f"CUDA error during synthesis: {error_msg}")
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                    raise SynthesisError(f"CUDA error: {error_msg}. Try restarting the server.")
                raise

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
                "long_text_chunking": True,  # Auto-chunk long texts
            },
            "limits": {
                "max_text_length": 50000,
                "chunk_size": MAX_CHUNK_LENGTH,
                "description": "Long texts are automatically split into chunks and concatenated"
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
