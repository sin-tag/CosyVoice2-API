import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from app.engine.base import TTSEngine

logger = logging.getLogger(__name__)

QWEN_LANG_MAP = {
    "zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean",
    "de": "German", "fr": "French", "ru": "Russian", "pt": "Portuguese",
    "es": "Spanish", "it": "Italian",
}
QWEN_LANG_CODES = list(QWEN_LANG_MAP.keys())

# Default ref_text when user doesn't provide one
DEFAULT_REF_TEXT = "Hello, how are you today? Nice to meet you."

# Max ref audio duration in seconds — longer audio is auto-trimmed for speed
MAX_REF_AUDIO_SEC = 8


class QwenEngine(TTSEngine):
    """Thin wrapper around qwen_tts.Qwen3TTSModel — matches official example exactly."""

    name = "qwen"
    supported_languages = QWEN_LANG_CODES

    def __init__(self, model_path: str, device: str = "cuda:0", dtype: str = "bfloat16"):
        self._model_path = model_path
        self._device = device
        self._dtype = dtype
        self._model = None

    async def load_model(self) -> None:
        logger.info("Loading Qwen3-TTS from %s on %s...", self._model_path, self._device)

        def _load():
            import torch
            from qwen_tts import Qwen3TTSModel

            dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}

            # Auto-detect flash_attention_2
            try:
                import flash_attn  # noqa: F401
                attn = "flash_attention_2"
            except ImportError:
                attn = "sdpa"
                logger.warning("flash-attn not installed, using sdpa. Install for 2-3x speed: pip install flash-attn")

            model = Qwen3TTSModel.from_pretrained(
                self._model_path,
                device_map=self._device,
                dtype=dtype_map.get(self._dtype, torch.bfloat16),
                attn_implementation=attn,
            )
            return model

        self._model = await asyncio.to_thread(_load)
        logger.info("Qwen3-TTS loaded on %s", self._device)

    async def unload_model(self) -> None:
        if self._model is not None:
            import torch
            del self._model
            self._model = None
            torch.cuda.empty_cache()

    def is_loaded(self) -> bool:
        return self._model is not None

    def _lang(self, code: str) -> str:
        return QWEN_LANG_MAP.get(code, "English")

    def _trim_ref_audio(self, audio_path: str) -> str:
        """Trim ref audio to MAX_REF_AUDIO_SEC if too long. Returns path (original or trimmed)."""
        import soundfile as sf
        info = sf.info(audio_path)
        if info.duration <= MAX_REF_AUDIO_SEC:
            return audio_path

        import os
        # Create trimmed version next to original
        base, ext = os.path.splitext(audio_path)
        trimmed_path = f"{base}_trimmed{ext}"
        if os.path.exists(trimmed_path):
            return trimmed_path

        data, sr = sf.read(audio_path, stop=int(MAX_REF_AUDIO_SEC * info.samplerate))
        sf.write(trimmed_path, data, sr)
        logger.info("Trimmed ref audio from %.1fs to %.1fs: %s", info.duration, MAX_REF_AUDIO_SEC, trimmed_path)
        return trimmed_path

    # ──── Core: exactly like the official example ────

    async def generate(
        self, text: str, language: str, voice_data: Any | None = None, **params,
    ) -> tuple[np.ndarray, int]:
        if voice_data is None:
            raise ValueError("Voice required. Upload via POST /api/v1/voices first.")

        lang = self._lang(language)
        ref_audio = self._trim_ref_audio(voice_data["ref_audio"])
        ref_text = voice_data.get("ref_text", "") or DEFAULT_REF_TEXT

        def _run():
            import torch
            with torch.inference_mode():
                wavs, sr = self._model.generate_voice_clone(
                    text=text,
                    language=lang,
                    ref_audio=ref_audio,
                    ref_text=ref_text,
                )
            audio = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            return audio.squeeze().astype(np.float32), sr

        return await asyncio.to_thread(_run)

    async def generate_dialogue(
        self,
        segments: list[dict],
        speaker_refs: dict[str, str],
        language: str = "en",
        speaker_ref_texts: dict[str, str] | None = None,
        **params,
    ) -> tuple[np.ndarray, int]:
        """Generate each segment with voice clone, concatenate with silence."""
        speaker_ref_texts = speaker_ref_texts or {}
        lang = self._lang(language)

        def _run():
            import torch
            parts = []
            sr = 24000

            with torch.inference_mode():
                for seg in segments:
                    ref_path = speaker_refs.get(seg["speaker"])
                    if not ref_path:
                        continue
                    ref_path = self._trim_ref_audio(ref_path)

                    ref_text = speaker_ref_texts.get(seg["speaker"], "") or DEFAULT_REF_TEXT

                    wavs, sr = self._model.generate_voice_clone(
                        text=seg["text"],
                        language=lang,
                        ref_audio=ref_path,
                        ref_text=ref_text,
                    )

                    audio = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
                    if hasattr(audio, "cpu"):
                        audio = audio.cpu().numpy()
                    parts.append(audio.squeeze().astype(np.float32))
                    parts.append(np.zeros(int(sr * 0.3), dtype=np.float32))  # 0.3s silence

            if not parts:
                raise RuntimeError("No audio generated")
            return np.concatenate(parts[:-1]), sr  # remove trailing silence

        return await asyncio.to_thread(_run)

    async def stream_generate(
        self, text: str, language: str, voice_data: Any | None = None, **params,
    ) -> AsyncIterator[np.ndarray]:
        audio, sr = await self.generate(text, language, voice_data, **params)
        yield audio

    # ──── Voice cache ────

    async def prepare_voice(self, audio_path: str, reference_text: str | None = None) -> Any:
        return {"ref_audio": audio_path, "ref_text": reference_text or ""}

    async def load_cached_voice(self, cache_path: str) -> Any:
        import torch
        return await asyncio.to_thread(torch.load, cache_path, map_location="cpu", weights_only=False)

    async def save_voice_cache(self, voice_data: Any, cache_path: str) -> None:
        import torch
        await asyncio.to_thread(torch.save, voice_data, cache_path)
