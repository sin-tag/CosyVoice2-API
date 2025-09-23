"""Streaming Synthesis Engine for CosyVoice2 API - Real-time audio streaming support"""
import asyncio
import logging
import time
import uuid
import io
import base64
from typing import AsyncGenerator, Optional, Dict, Any, Tuple
import torch
import torchaudio
import numpy as np

from app.models.streaming import (
    StreamingSynthesisRequest, StreamingChunkMetadata, StreamingQuality,
    StreamingError, HTTPStreamingRequest
)
from app.models.voice import AudioFormat
from app.core.synthesis_engine import SynthesisEngine
from app.core.exceptions import SynthesisError, VoiceNotFoundError
from cosyvoice.utils.file_utils import load_wav
from cosyvoice.utils.common import set_all_random_seed
from app.core.synthesis_engine import postprocess

logger = logging.getLogger(__name__)

class StreamingSynthesisEngine:
    """Enhanced synthesis engine with real-time streaming capabilities"""
    
    def __init__(self, synthesis_engine: SynthesisEngine):
        self.synthesis_engine = synthesis_engine
        self.voice_manager = synthesis_engine.voice_manager
        
        # Streaming configuration
        self.quality_settings = {
            StreamingQuality.LOW: {"sample_rate": 16000, "chunk_duration": 0.5},
            StreamingQuality.MEDIUM: {"sample_rate": 22050, "chunk_duration": 0.3},
            StreamingQuality.HIGH: {"sample_rate": 44100, "chunk_duration": 0.2}
        }
        
    async def stream_cross_lingual_synthesis(
        self, 
        request: StreamingSynthesisRequest
    ) -> AsyncGenerator[Tuple[bytes, StreamingChunkMetadata], None]:
        """Stream cross-lingual synthesis with real-time audio chunks"""
        
        logger.info(f"Starting streaming synthesis for text: {request.text[:50]}...")
        
        try:
            # Get model
            model = self.voice_manager._get_active_model()
            if not model:
                raise SynthesisError("Model not available")
            
            # Get cached voice
            voice = self.voice_manager.voice_cache.voices.get(request.voice_id)
            if not voice:
                raise VoiceNotFoundError(f"Voice '{request.voice_id}' not found")
            
            # Get quality settings
            quality_config = self.quality_settings[request.quality]
            target_sample_rate = quality_config["sample_rate"]
            chunk_duration = quality_config["chunk_duration"]
            
            # Calculate chunk size in samples
            chunk_size_samples = int(target_sample_rate * chunk_duration)
            
            # Load and process voice audio
            prompt_speech_16k = postprocess(load_wav(voice.audio_file_path, 16000), 16000)
            
            # Set random seed for reproducible results
            set_all_random_seed(42)
            
            # Start synthesis in executor to avoid blocking
            loop = asyncio.get_event_loop()
            synthesis_generator = await loop.run_in_executor(
                None, self._create_synthesis_generator, 
                model, request.text, prompt_speech_16k, request.speed
            )
            
            # Stream audio chunks
            chunk_index = 0
            audio_buffer = []
            total_samples = 0
            start_time = time.time()
            
            async for model_output in self._async_generator_wrapper(synthesis_generator):
                if 'tts_speech' in model_output:
                    # Get audio chunk as numpy array
                    audio_chunk = model_output['tts_speech'].numpy().flatten()
                    audio_buffer.extend(audio_chunk)
                    total_samples += len(audio_chunk)
                    
                    # Process complete chunks
                    while len(audio_buffer) >= chunk_size_samples:
                        # Extract chunk
                        chunk_data = np.array(audio_buffer[:chunk_size_samples], dtype=np.float32)
                        audio_buffer = audio_buffer[chunk_size_samples:]
                        
                        # Resample if needed
                        if model.sample_rate != target_sample_rate:
                            chunk_data = self._resample_chunk(
                                chunk_data, model.sample_rate, target_sample_rate
                            )
                        
                        # Encode chunk to bytes
                        chunk_bytes = await self._encode_audio_chunk(
                            chunk_data, target_sample_rate, request.format,
                            is_first_chunk=(chunk_index == 0),
                            estimated_total_samples=None  # We don't know total yet
                        )
                        
                        # Create metadata
                        metadata = StreamingChunkMetadata(
                            chunk_index=chunk_index,
                            chunk_size=len(chunk_bytes),
                            timestamp=time.time(),
                            is_final=False,
                            sample_rate=target_sample_rate,
                            channels=1
                        )
                        
                        logger.debug(f"Yielding chunk {chunk_index}, size: {len(chunk_bytes)} bytes")
                        yield chunk_bytes, metadata
                        chunk_index += 1
            
            # Process remaining audio in buffer (final chunk)
            if audio_buffer:
                chunk_data = np.array(audio_buffer, dtype=np.float32)
                
                # Resample if needed
                if model.sample_rate != target_sample_rate:
                    chunk_data = self._resample_chunk(
                        chunk_data, model.sample_rate, target_sample_rate
                    )
                
                # Encode final chunk
                chunk_bytes = await self._encode_audio_chunk(
                    chunk_data, target_sample_rate, request.format,
                    is_first_chunk=(chunk_index == 0),
                    estimated_total_samples=None
                )
                
                # Create final metadata
                metadata = StreamingChunkMetadata(
                    chunk_index=chunk_index,
                    chunk_size=len(chunk_bytes),
                    total_chunks=chunk_index + 1,
                    timestamp=time.time(),
                    is_final=True,
                    sample_rate=target_sample_rate,
                    channels=1
                )
                
                logger.info(f"Yielding final chunk {chunk_index}, total chunks: {chunk_index + 1}")
                yield chunk_bytes, metadata
            
            synthesis_time = time.time() - start_time
            logger.info(f"Streaming synthesis completed in {synthesis_time:.2f}s, {chunk_index + 1} chunks")
            
        except Exception as e:
            logger.error(f"Streaming synthesis failed: {e}")
            raise StreamingError(
                error_type="synthesis_error",
                error_code="STREAMING_SYNTHESIS_FAILED",
                message=f"Streaming synthesis failed: {str(e)}",
                timestamp=time.time(),
                recoverable=False
            )
    
    def _create_synthesis_generator(self, model, text: str, prompt_speech_16k, speed: float):
        """Create synthesis generator in sync context"""
        try:
            if hasattr(model, 'inference_cross_lingual'):
                return model.inference_cross_lingual(
                    text, prompt_speech_16k, stream=True, speed=speed
                )
            else:
                # Fallback to zero-shot
                return model.inference_zero_shot(
                    text, "", prompt_speech_16k, stream=True, speed=speed
                )
        except Exception as e:
            logger.error(f"Failed to create synthesis generator: {e}")
            raise SynthesisError(f"Failed to create synthesis generator: {str(e)}")
    
    async def _async_generator_wrapper(self, sync_generator):
        """Wrap synchronous generator to work with async/await"""
        loop = asyncio.get_event_loop()
        
        def get_next():
            try:
                return next(sync_generator)
            except StopIteration:
                return None
        
        while True:
            try:
                result = await loop.run_in_executor(None, get_next)
                if result is None:
                    break
                yield result
            except Exception as e:
                logger.error(f"Error in async generator wrapper: {e}")
                break
    
    def _resample_chunk(self, audio_data: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        """Resample audio chunk to target sample rate"""
        if source_rate == target_rate:
            return audio_data
        
        try:
            # Convert to tensor for resampling
            audio_tensor = torch.from_numpy(audio_data).unsqueeze(0)
            resampled = torchaudio.functional.resample(
                audio_tensor, source_rate, target_rate
            )
            return resampled.squeeze(0).numpy()
        except Exception as e:
            logger.warning(f"Resampling failed, using original: {e}")
            return audio_data
    
    async def _encode_audio_chunk(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        format: AudioFormat,
        is_first_chunk: bool = False,
        estimated_total_samples: int = None
    ) -> bytes:
        """Encode audio chunk to specified format with proper streaming support"""
        try:
            if format == AudioFormat.WAV:
                if is_first_chunk:
                    # For first chunk, create WAV with header
                    return self._create_wav_with_header(audio_data, sample_rate, estimated_total_samples)
                else:
                    # For subsequent chunks, return only raw PCM data
                    return self._encode_raw_pcm(audio_data)
            else:
                # For non-WAV formats, use complete file encoding per chunk
                # This is not ideal for streaming but works for compatibility
                audio_tensor = torch.from_numpy(audio_data).unsqueeze(0)
                buffer = io.BytesIO()

                if format == AudioFormat.MP3:
                    # Convert to WAV first, then encode to MP3 if needed
                    torchaudio.save(buffer, audio_tensor, sample_rate, format="wav")
                else:
                    # Default to WAV
                    torchaudio.save(buffer, audio_tensor, sample_rate, format="wav")

                buffer.seek(0)
                return buffer.getvalue()

        except Exception as e:
            logger.error(f"Audio encoding failed: {e}")
            raise StreamingError(
                error_type="encoding_error",
                error_code="AUDIO_ENCODING_FAILED",
                message=f"Failed to encode audio chunk: {str(e)}",
                timestamp=time.time(),
                recoverable=False
            )

    def _create_wav_with_header(self, audio_data: np.ndarray, sample_rate: int, estimated_total_samples: int = None) -> bytes:
        """Create WAV file with proper header for streaming"""
        # Convert to 16-bit PCM
        audio_int16 = (audio_data * 32767).astype(np.int16)

        # Estimate total file size (will be updated if known)
        if estimated_total_samples:
            data_size = estimated_total_samples * 2  # 16-bit = 2 bytes per sample
        else:
            # Use a large placeholder that will work for most cases
            data_size = len(audio_int16) * 100  # Rough estimate

        # WAV header
        header = bytearray()
        header.extend(b'RIFF')  # ChunkID
        header.extend((36 + data_size).to_bytes(4, 'little'))  # ChunkSize
        header.extend(b'WAVE')  # Format
        header.extend(b'fmt ')  # Subchunk1ID
        header.extend((16).to_bytes(4, 'little'))  # Subchunk1Size (PCM)
        header.extend((1).to_bytes(2, 'little'))   # AudioFormat (PCM)
        header.extend((1).to_bytes(2, 'little'))   # NumChannels (mono)
        header.extend(sample_rate.to_bytes(4, 'little'))  # SampleRate
        header.extend((sample_rate * 2).to_bytes(4, 'little'))  # ByteRate
        header.extend((2).to_bytes(2, 'little'))   # BlockAlign
        header.extend((16).to_bytes(2, 'little'))  # BitsPerSample
        header.extend(b'data')  # Subchunk2ID
        header.extend(data_size.to_bytes(4, 'little'))  # Subchunk2Size

        # Combine header with audio data
        return bytes(header) + audio_int16.tobytes()

    def _encode_raw_pcm(self, audio_data: np.ndarray) -> bytes:
        """Encode audio data as raw 16-bit PCM for streaming"""
        # Convert to 16-bit PCM
        audio_int16 = (audio_data * 32767).astype(np.int16)
        return audio_int16.tobytes()
    
    async def get_streaming_headers(self, format: AudioFormat) -> Dict[str, str]:
        """Get appropriate HTTP headers for streaming audio"""
        content_type_map = {
            AudioFormat.WAV: "audio/wav",
            AudioFormat.MP3: "audio/mpeg",
            AudioFormat.FLAC: "audio/flac",
            AudioFormat.M4A: "audio/mp4"
        }
        
        return {
            "Content-Type": content_type_map.get(format, "audio/wav"),
            "Transfer-Encoding": "chunked",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff"
        }
