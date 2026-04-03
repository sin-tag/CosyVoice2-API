"""Audio conversion utilities."""

import io
import logging
import os

import numpy as np

logger = logging.getLogger(__name__)


def audio_to_mp3(audio: np.ndarray, sr: int = 24000, bitrate: str = "128k") -> bytes:
    """Convert float32 audio array to MP3 bytes."""
    from pydub import AudioSegment

    # float32 → int16
    pcm16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)

    segment = AudioSegment(
        data=pcm16.tobytes(),
        sample_width=2,
        frame_rate=sr,
        channels=1,
    )

    buf = io.BytesIO()
    segment.export(buf, format="mp3", bitrate=bitrate)
    return buf.getvalue()


def save_audio_mp3(audio: np.ndarray, path: str, sr: int = 24000, bitrate: str = "128k") -> None:
    """Save float32 audio array as MP3 file."""
    mp3_bytes = audio_to_mp3(audio, sr, bitrate)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(mp3_bytes)
