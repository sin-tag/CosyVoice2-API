import asyncio
import logging
import os
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

MAX_REF_AUDIO_SEC = 5
DEFAULT_REF_TEXT = "Hello, how are you today? Nice to meet you."


class QwenCustomVoiceEngine(TTSEngine):
    """Adapter for Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice.

    1.7B params, 10 languages, custom voice with speaker + instruct control.
    Supports: generate_custom_voice (speaker + emotion instruct)
              generate_voice_clone (ref audio cloning)
    """

    name = "qwen"
    supported_languages = QWEN_LANG_CODES

    def __init__(self, model_path: str, device: str = "cuda:0", dtype: str = "bfloat16"):
        self._model_path = model_path
        self._device = device
        self._dtype = dtype
        self._model = None

    async def load_model(self) -> None:
        logger.info("Loading Qwen3-TTS-CustomVoice from %s on %s...", self._model_path, self._device)

        def _load():
            import torch
            from qwen_tts import Qwen3TTSModel

            dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}

            try:
                import flash_attn  # noqa: F401
                attn = "flash_attention_2"
            except ImportError:
                attn = "sdpa"
                logger.warning("flash-attn not installed, using sdpa")

            model = Qwen3TTSModel.from_pretrained(
                self._model_path,
                device_map=self._device,
                dtype=dtype_map.get(self._dtype, torch.bfloat16),
                attn_implementation=attn,
            )
            return model

        self._model = await asyncio.to_thread(_load)
        logger.info("Qwen3-TTS-CustomVoice loaded on %s", self._device)

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
        import soundfile as sf
        info = sf.info(audio_path)
        if info.duration <= MAX_REF_AUDIO_SEC:
            return audio_path
        base, ext = os.path.splitext(audio_path)
        trimmed_path = f"{base}_trimmed{ext}"
        if os.path.exists(trimmed_path):
            return trimmed_path
        data, sr = sf.read(audio_path, stop=int(MAX_REF_AUDIO_SEC * info.samplerate))
        sf.write(trimmed_path, data, sr)
        logger.info("Trimmed ref audio from %.1fs to %.1fs", info.duration, MAX_REF_AUDIO_SEC)
        return trimmed_path

    # ──── Custom Voice (speaker + instruct) ────

    async def generate_custom(
        self, text: str, language: str, speaker: str = "Vivian", instruct: str = "", **params,
    ) -> tuple[np.ndarray, int]:
        """Generate with built-in speaker + emotion instruct."""
        lang = self._lang(language)
        speed = params.get("speed", 0.8)

        def _run():
            import torch
            with torch.inference_mode():
                kwargs = {"text": text, "language": lang, "speaker": speaker}
                if instruct:
                    kwargs["instruct"] = instruct
                wavs, sr = self._model.generate_custom_voice(**kwargs)
            audio = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            return audio.squeeze().astype(np.float32), sr

        return await asyncio.to_thread(_run)

    # ──── Voice Clone (ref audio) ────

    async def generate(
        self, text: str, language: str, voice_data: Any | None = None, **params,
    ) -> tuple[np.ndarray, int]:
        if voice_data is None:
            raise ValueError("Voice required. Upload via POST /api/v1/voices first.")

        ref_audio = voice_data["ref_audio"]
        if ref_audio.startswith(("http://", "https://")):
            ref_audio = _download_url(ref_audio)
        ref_audio = self._trim_ref_audio(ref_audio)
        ref_text = voice_data.get("ref_text", "") or DEFAULT_REF_TEXT
        speed = params.get("speed", 0.8)

        def _run():
            import torch
            with torch.inference_mode():
                wavs, sr = self._model.generate_voice_clone(
                    text=text, language=self._lang(language),
                    ref_audio=ref_audio, ref_text=ref_text,
                )
            audio = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            return audio.squeeze().astype(np.float32), sr

        return await asyncio.to_thread(_run)

    # ──── Comic Dubbing ────

    async def generate_dialogue(
        self,
        segments: list[dict],
        speaker_refs: dict[str, str],
        language: str = "en",
        speaker_ref_texts: dict[str, str] | None = None,
        speaker_instructs: dict[str, str] | None = None,
        **params,
    ) -> tuple[np.ndarray, int]:
        """Generate each segment, concatenate. Supports ref audio OR built-in speaker+instruct."""
        speaker_ref_texts = speaker_ref_texts or {}
        speaker_instructs = speaker_instructs or {}
        lang = self._lang(language)

        def _run():
            import torch
            parts = []
            sr = 24000

            with torch.inference_mode():
                for seg in segments:
                    speaker_name = seg["speaker"]
                    ref_path = speaker_refs.get(speaker_name)
                    instruct = speaker_instructs.get(speaker_name, "")

                    if ref_path:
                        # Voice clone mode
                        if ref_path.startswith(("http://", "https://")):
                            ref_path = _download_url(ref_path)
                        ref_path = self._trim_ref_audio(ref_path)
                        ref_text = speaker_ref_texts.get(speaker_name, "") or DEFAULT_REF_TEXT

                        wavs, sr = self._model.generate_voice_clone(
                            text=seg["text"], language=lang,
                            ref_audio=ref_path, ref_text=ref_text,
                        )
                    else:
                        # Custom voice mode (built-in speaker)
                        kwargs = {"text": seg["text"], "language": lang, "speaker": speaker_name}
                        if instruct:
                            kwargs["instruct"] = instruct
                        wavs, sr = self._model.generate_custom_voice(**kwargs)

                    audio = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
                    if hasattr(audio, "cpu"):
                        audio = audio.cpu().numpy()
                    parts.append(audio.squeeze().astype(np.float32))
                    parts.append(np.zeros(int(sr * 0.3), dtype=np.float32))

            if not parts:
                raise RuntimeError("No audio generated")
            return np.concatenate(parts[:-1]), sr

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


def _download_url(url: str, storage_dir: str = "./storage/voices") -> str:
    import hashlib
    import urllib.request
    os.makedirs(storage_dir, exist_ok=True)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    ext = os.path.splitext(url.split("?")[0])[1] or ".wav"
    local_path = os.path.join(storage_dir, f"dl_{url_hash}{ext}")
    if os.path.exists(local_path):
        return local_path
    logger.info("Downloading ref audio: %s", url)
    urllib.request.urlretrieve(url, local_path)
    return local_path
