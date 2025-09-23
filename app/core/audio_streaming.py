"""Audio Format Streaming Support - Optimized encoding and chunking for different audio formats"""
import io
import logging
import struct
import wave
from typing import Optional, Dict, Any, Tuple, Generator
import numpy as np
import torch
import torchaudio

from app.models.voice import AudioFormat
from app.models.streaming import StreamingQuality

logger = logging.getLogger(__name__)

class AudioStreamEncoder:
    """Handles encoding of audio chunks for different formats with streaming optimization"""
    
    def __init__(self):
        self.format_encoders = {
            AudioFormat.WAV: self._encode_wav_chunk,
            AudioFormat.MP3: self._encode_mp3_chunk,
            AudioFormat.FLAC: self._encode_flac_chunk,
            AudioFormat.M4A: self._encode_m4a_chunk
        }
        
        # Optimal chunk sizes for different formats (in samples)
        self.optimal_chunk_sizes = {
            AudioFormat.WAV: 2048,   # Small chunks for low latency
            AudioFormat.MP3: 4096,   # Larger chunks for compression efficiency
            AudioFormat.FLAC: 4096,  # Larger chunks for compression
            AudioFormat.M4A: 4096    # Larger chunks for compression
        }
        
        # Quality settings for streaming
        self.quality_settings = {
            StreamingQuality.LOW: {
                "sample_rate": 16000,
                "bitrate": 64000,
                "channels": 1
            },
            StreamingQuality.MEDIUM: {
                "sample_rate": 22050,
                "bitrate": 128000,
                "channels": 1
            },
            StreamingQuality.HIGH: {
                "sample_rate": 44100,
                "bitrate": 256000,
                "channels": 1
            }
        }
    
    def get_optimal_chunk_size(self, format: AudioFormat, quality: StreamingQuality) -> int:
        """Get optimal chunk size for format and quality"""
        base_size = self.optimal_chunk_sizes.get(format, 2048)
        
        # Adjust based on quality
        if quality == StreamingQuality.LOW:
            return base_size // 2  # Smaller chunks for lower latency
        elif quality == StreamingQuality.HIGH:
            return base_size * 2   # Larger chunks for better quality
        else:
            return base_size
    
    def get_streaming_headers(self, format: AudioFormat, quality: StreamingQuality) -> Dict[str, str]:
        """Get HTTP headers for streaming audio format"""
        content_type_map = {
            AudioFormat.WAV: "audio/wav",
            AudioFormat.MP3: "audio/mpeg",
            AudioFormat.FLAC: "audio/flac",
            AudioFormat.M4A: "audio/mp4"
        }
        
        quality_config = self.quality_settings[quality]
        
        headers = {
            "Content-Type": content_type_map.get(format, "audio/wav"),
            "Transfer-Encoding": "chunked",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
            "X-Audio-Sample-Rate": str(quality_config["sample_rate"]),
            "X-Audio-Channels": str(quality_config["channels"]),
            "X-Audio-Format": format.value
        }
        
        if format in [AudioFormat.MP3, AudioFormat.M4A]:
            headers["X-Audio-Bitrate"] = str(quality_config["bitrate"])
        
        return headers
    
    def encode_audio_chunk(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int,
        format: AudioFormat,
        quality: StreamingQuality,
        chunk_index: int = 0,
        is_first_chunk: bool = False,
        is_final_chunk: bool = False
    ) -> bytes:
        """Encode audio chunk to specified format with streaming optimization"""
        
        encoder = self.format_encoders.get(format, self._encode_wav_chunk)
        
        try:
            return encoder(
                audio_data, sample_rate, quality, 
                chunk_index, is_first_chunk, is_final_chunk
            )
        except Exception as e:
            logger.error(f"Failed to encode audio chunk in {format.value} format: {e}")
            # Fallback to WAV encoding
            return self._encode_wav_chunk(
                audio_data, sample_rate, quality,
                chunk_index, is_first_chunk, is_final_chunk
            )
    
    def _encode_wav_chunk(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int,
        quality: StreamingQuality,
        chunk_index: int,
        is_first_chunk: bool,
        is_final_chunk: bool
    ) -> bytes:
        """Encode audio chunk as WAV format"""
        
        # Convert to 16-bit PCM
        if audio_data.dtype != np.int16:
            # Normalize to [-1, 1] if needed
            if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                audio_data = np.clip(audio_data, -1.0, 1.0)
                audio_data = (audio_data * 32767).astype(np.int16)
            else:
                audio_data = audio_data.astype(np.int16)
        
        # Create WAV chunk
        buffer = io.BytesIO()
        
        if is_first_chunk:
            # Write WAV header for first chunk
            channels = 1
            sample_width = 2  # 16-bit
            
            # Estimate total length (we'll update this in final chunk)
            estimated_frames = len(audio_data) * 10  # Rough estimate
            
            buffer.write(b'RIFF')
            buffer.write(struct.pack('<I', 36 + estimated_frames * channels * sample_width))
            buffer.write(b'WAVE')
            buffer.write(b'fmt ')
            buffer.write(struct.pack('<I', 16))  # fmt chunk size
            buffer.write(struct.pack('<H', 1))   # PCM format
            buffer.write(struct.pack('<H', channels))
            buffer.write(struct.pack('<I', sample_rate))
            buffer.write(struct.pack('<I', sample_rate * channels * sample_width))
            buffer.write(struct.pack('<H', channels * sample_width))
            buffer.write(struct.pack('<H', sample_width * 8))
            buffer.write(b'data')
            buffer.write(struct.pack('<I', estimated_frames * channels * sample_width))
        
        # Write audio data
        buffer.write(audio_data.tobytes())
        
        return buffer.getvalue()
    
    def _encode_mp3_chunk(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int,
        quality: StreamingQuality,
        chunk_index: int,
        is_first_chunk: bool,
        is_final_chunk: bool
    ) -> bytes:
        """Encode audio chunk as MP3 format (simplified - would need proper MP3 encoder)"""
        
        # For now, encode as WAV and add MP3 headers
        # In production, you'd use a proper MP3 encoder like lame or ffmpeg
        
        logger.warning("MP3 streaming not fully implemented, falling back to WAV")
        return self._encode_wav_chunk(
            audio_data, sample_rate, quality,
            chunk_index, is_first_chunk, is_final_chunk
        )
    
    def _encode_flac_chunk(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int,
        quality: StreamingQuality,
        chunk_index: int,
        is_first_chunk: bool,
        is_final_chunk: bool
    ) -> bytes:
        """Encode audio chunk as FLAC format"""
        
        try:
            # Convert to tensor for torchaudio
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
                if np.max(np.abs(audio_data)) > 1.0:
                    audio_data = audio_data / 32767.0  # Normalize from int16 range
            
            audio_tensor = torch.from_numpy(audio_data).unsqueeze(0)
            
            # Encode to FLAC using torchaudio
            buffer = io.BytesIO()
            torchaudio.save(buffer, audio_tensor, sample_rate, format="flac")
            buffer.seek(0)
            
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"FLAC encoding failed: {e}")
            return self._encode_wav_chunk(
                audio_data, sample_rate, quality,
                chunk_index, is_first_chunk, is_final_chunk
            )
    
    def _encode_m4a_chunk(
        self, 
        audio_data: np.ndarray, 
        sample_rate: int,
        quality: StreamingQuality,
        chunk_index: int,
        is_first_chunk: bool,
        is_final_chunk: bool
    ) -> bytes:
        """Encode audio chunk as M4A format"""
        
        # M4A encoding is complex and would require external libraries
        # For now, fall back to WAV
        logger.warning("M4A streaming not implemented, falling back to WAV")
        return self._encode_wav_chunk(
            audio_data, sample_rate, quality,
            chunk_index, is_first_chunk, is_final_chunk
        )

class StreamingAudioBuffer:
    """Buffer for managing audio chunks during streaming"""
    
    def __init__(self, chunk_size: int, format: AudioFormat, sample_rate: int):
        self.chunk_size = chunk_size
        self.format = format
        self.sample_rate = sample_rate
        self.buffer = []
        self.total_samples = 0
        self.encoder = AudioStreamEncoder()
    
    def add_samples(self, samples: np.ndarray) -> Generator[bytes, None, None]:
        """Add samples to buffer and yield complete chunks"""
        
        self.buffer.extend(samples.flatten())
        
        # Yield complete chunks
        while len(self.buffer) >= self.chunk_size:
            chunk_data = np.array(self.buffer[:self.chunk_size], dtype=np.float32)
            self.buffer = self.buffer[self.chunk_size:]
            
            # Encode chunk
            chunk_bytes = self.encoder.encode_audio_chunk(
                chunk_data, 
                self.sample_rate, 
                self.format,
                StreamingQuality.MEDIUM,  # Default quality
                self.total_samples // self.chunk_size,
                self.total_samples == 0,  # is_first_chunk
                False  # is_final_chunk
            )
            
            self.total_samples += len(chunk_data)
            yield chunk_bytes
    
    def flush(self) -> Optional[bytes]:
        """Flush remaining samples in buffer as final chunk"""
        
        if not self.buffer:
            return None
        
        chunk_data = np.array(self.buffer, dtype=np.float32)
        self.buffer = []
        
        # Encode final chunk
        chunk_bytes = self.encoder.encode_audio_chunk(
            chunk_data,
            self.sample_rate,
            self.format,
            StreamingQuality.MEDIUM,
            self.total_samples // self.chunk_size,
            self.total_samples == 0,  # is_first_chunk
            True  # is_final_chunk
        )
        
        return chunk_bytes

def optimize_chunk_size_for_network(
    base_chunk_size: int, 
    format: AudioFormat, 
    target_latency_ms: float = 100.0
) -> int:
    """Optimize chunk size for network streaming based on target latency"""
    
    # Network optimization factors
    format_multipliers = {
        AudioFormat.WAV: 1.0,    # No compression
        AudioFormat.MP3: 0.3,    # ~70% compression
        AudioFormat.FLAC: 0.6,   # ~40% compression
        AudioFormat.M4A: 0.4     # ~60% compression
    }
    
    # Adjust chunk size based on format compression
    multiplier = format_multipliers.get(format, 1.0)
    optimized_size = int(base_chunk_size * multiplier)
    
    # Ensure minimum and maximum bounds
    min_chunk_size = 512
    max_chunk_size = 8192
    
    return max(min_chunk_size, min(max_chunk_size, optimized_size))
