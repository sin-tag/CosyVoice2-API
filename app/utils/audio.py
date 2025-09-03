"""
Audio processing utilities for CosyVoice2 API
"""

import os
import tempfile
import librosa
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Union
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.models.voice import AudioFormat
from app.core.config import settings


class AudioProcessor:
    """Audio processing utilities"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    async def validate_audio_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate audio file format and properties
        Returns: (is_valid, error_message)
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return False, "Audio file does not exist"
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > settings.MAX_FILE_SIZE:
                return False, f"File size ({file_size} bytes) exceeds maximum allowed size ({settings.MAX_FILE_SIZE} bytes)"
            
            # Load audio to validate format and get properties
            audio_info = await self._get_audio_info(file_path)
            if not audio_info:
                return False, "Invalid audio file format or corrupted file"
            
            duration, sample_rate, channels = audio_info
            
            # Check duration
            if duration > settings.MAX_AUDIO_DURATION:
                return False, f"Audio duration ({duration:.2f}s) exceeds maximum allowed duration ({settings.MAX_AUDIO_DURATION}s)"
            
            # Check if audio is too short (minimum 0.5 seconds)
            if duration < 0.5:
                return False, "Audio duration is too short (minimum 0.5 seconds required)"
            
            return True, None
            
        except Exception as e:
            return False, f"Error validating audio file: {str(e)}"
    
    async def _get_audio_info(self, file_path: str) -> Optional[Tuple[float, int, int]]:
        """Get audio file information (duration, sample_rate, channels)"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, 
                self._get_audio_info_sync, 
                file_path
            )
        except Exception:
            return None
    
    def _get_audio_info_sync(self, file_path: str) -> Tuple[float, int, int]:
        """Synchronous version of get_audio_info"""
        try:
            # Try with librosa first
            y, sr = librosa.load(file_path, sr=None)
            duration = len(y) / sr
            channels = 1 if y.ndim == 1 else y.shape[0]
            return duration, sr, channels
        except Exception:
            # Fallback to soundfile
            with sf.SoundFile(file_path) as f:
                duration = len(f) / f.samplerate
                return duration, f.samplerate, f.channels
    
    async def convert_audio_format(self, input_path: str, output_path: str, 
                                 target_format: AudioFormat, 
                                 target_sample_rate: Optional[int] = None) -> bool:
        """
        Convert audio file to target format and sample rate
        Returns: success status
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self._convert_audio_format_sync,
                input_path, output_path, target_format, target_sample_rate
            )
        except Exception as e:
            print(f"Error converting audio format: {e}")
            return False
    
    def _convert_audio_format_sync(self, input_path: str, output_path: str,
                                 target_format: AudioFormat,
                                 target_sample_rate: Optional[int] = None) -> bool:
        """Synchronous version of convert_audio_format"""
        try:
            # Load audio
            y, sr = librosa.load(input_path, sr=target_sample_rate)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save in target format
            if target_format == AudioFormat.WAV:
                sf.write(output_path, y, sr, format='WAV')
            elif target_format == AudioFormat.MP3:
                # For MP3, we need to use a different approach
                # Convert to WAV first, then use external tool or library
                temp_wav = output_path.replace('.mp3', '_temp.wav')
                sf.write(temp_wav, y, sr, format='WAV')
                
                # Use ffmpeg if available, otherwise keep as WAV
                try:
                    import subprocess
                    subprocess.run([
                        'ffmpeg', '-i', temp_wav, '-codec:a', 'libmp3lame', 
                        '-b:a', '192k', output_path, '-y'
                    ], check=True, capture_output=True)
                    os.remove(temp_wav)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Fallback: rename WAV to MP3 (not ideal but functional)
                    os.rename(temp_wav, output_path)
                    
            elif target_format == AudioFormat.FLAC:
                sf.write(output_path, y, sr, format='FLAC')
            else:
                # Default to WAV for unsupported formats
                sf.write(output_path, y, sr, format='WAV')
            
            return True
            
        except Exception as e:
            print(f"Error in sync audio conversion: {e}")
            return False
    
    async def resample_audio(self, input_path: str, output_path: str, 
                           target_sample_rate: int) -> bool:
        """
        Resample audio to target sample rate
        Returns: success status
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self._resample_audio_sync,
                input_path, output_path, target_sample_rate
            )
        except Exception as e:
            print(f"Error resampling audio: {e}")
            return False
    
    def _resample_audio_sync(self, input_path: str, output_path: str, 
                           target_sample_rate: int) -> bool:
        """Synchronous version of resample_audio"""
        try:
            # Load and resample
            y, sr = librosa.load(input_path, sr=target_sample_rate)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save resampled audio
            sf.write(output_path, y, target_sample_rate)
            return True
            
        except Exception as e:
            print(f"Error in sync audio resampling: {e}")
            return False
    
    async def normalize_audio(self, input_path: str, output_path: str, 
                            target_db: float = -20.0) -> bool:
        """
        Normalize audio to target dB level
        Returns: success status
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor,
                self._normalize_audio_sync,
                input_path, output_path, target_db
            )
        except Exception as e:
            print(f"Error normalizing audio: {e}")
            return False
    
    def _normalize_audio_sync(self, input_path: str, output_path: str, 
                            target_db: float = -20.0) -> bool:
        """Synchronous version of normalize_audio"""
        try:
            # Load audio
            y, sr = librosa.load(input_path, sr=None)
            
            # Calculate current RMS
            rms = np.sqrt(np.mean(y**2))
            if rms == 0:
                return False  # Silent audio
            
            # Calculate target amplitude
            target_rms = 10**(target_db / 20.0)
            
            # Normalize
            y_normalized = y * (target_rms / rms)
            
            # Ensure no clipping
            if np.max(np.abs(y_normalized)) > 1.0:
                y_normalized = y_normalized / np.max(np.abs(y_normalized)) * 0.95
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Save normalized audio
            sf.write(output_path, y_normalized, sr)
            return True
            
        except Exception as e:
            print(f"Error in sync audio normalization: {e}")
            return False
    
    def get_supported_formats(self) -> list[str]:
        """Get list of supported audio formats"""
        return [fmt.value for fmt in AudioFormat]
    
    def get_file_extension(self, format: AudioFormat) -> str:
        """Get file extension for audio format"""
        return f".{format.value}"
    
    async def cleanup(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)


# Global audio processor instance
audio_processor = AudioProcessor()
