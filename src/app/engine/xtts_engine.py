import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from app.engine.base import TTSEngine

logger = logging.getLogger(__name__)

MAX_REF_AUDIO_SEC = 5
DEFAULT_REF_TEXT = "Hello, how are you today? Nice to meet you."

XTTS_LANGUAGES = [
    "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru",
    "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi",
]


class XttsEngine(TTSEngine):
    """Adapter for coqui/XTTS-v2. 17 languages, voice cloning, streaming."""

    name = "xtts"
    supported_languages = XTTS_LANGUAGES

    def __init__(self, model_path: str = "tts_models/multilingual/multi-dataset/xtts_v2", device: str = "cuda:0", **kwargs):
        self._model_path = model_path
        self._device = device
        self._tts = None

    async def load_model(self) -> None:
        logger.info("Loading XTTS-v2 on %s...", self._device)

        def _load():
            os.environ["COQUI_TOS_AGREED"] = "1"
            from TTS.api import TTS
            tts = TTS(self._model_path).to(self._device)
            return tts

        self._tts = await asyncio.to_thread(_load)
        logger.info("XTTS-v2 loaded on %s", self._device)

    async def unload_model(self) -> None:
        if self._tts is not None:
            import torch
            del self._tts
            self._tts = None
            torch.cuda.empty_cache()

    def is_loaded(self) -> bool:
        return self._tts is not None

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

    def _map_lang(self, lang: str) -> str:
        """Map 'zh' → 'zh-cn' for XTTS compatibility."""
        if lang == "zh":
            return "zh-cn"
        return lang

    async def generate(
        self, text: str, language: str, voice_data: Any | None = None, **params,
    ) -> tuple[np.ndarray, int]:
        if voice_data is None:
            raise ValueError("Voice required. Upload via POST /api/v1/voices first.")

        ref_audio = _download_if_url(voice_data["ref_audio"])
        ref_audio = self._trim_ref_audio(ref_audio)
        lang = self._map_lang(language)

        def _run():
            import torch
            with torch.inference_mode():
                wav = self._tts.tts(text=text, speaker_wav=ref_audio, language=lang)
            audio = np.array(wav, dtype=np.float32)
            return audio, 24000

        return await asyncio.to_thread(_run)

    async def generate_dialogue(
        self,
        segments: list[dict],
        speaker_refs: dict[str, str],
        language: str = "en",
        speaker_ref_texts: dict[str, str] | None = None,
        **params,
    ) -> tuple[np.ndarray, int]:
        lang = self._map_lang(language)

        def _run():
            import torch
            parts = []
            sr = 24000

            with torch.inference_mode():
                for seg in segments:
                    ref_path = speaker_refs.get(seg["speaker"])
                    if not ref_path:
                        continue
                    ref_path = _download_if_url(ref_path)
                    ref_path = self._trim_ref_audio(ref_path)

                    wav = self._tts.tts(text=seg["text"], speaker_wav=ref_path, language=lang)
                    parts.append(np.array(wav, dtype=np.float32))
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

    async def prepare_voice(self, audio_path: str, reference_text: str | None = None) -> Any:
        audio_path = _download_if_url(audio_path)
        return {"ref_audio": audio_path, "ref_text": reference_text or ""}

    async def load_cached_voice(self, cache_path: str) -> Any:
        import torch
        return await asyncio.to_thread(torch.load, cache_path, map_location="cpu", weights_only=False)

    async def save_voice_cache(self, voice_data: Any, cache_path: str) -> None:
        import torch
        await asyncio.to_thread(torch.save, voice_data, cache_path)


def _download_if_url(path_or_url: str, storage_dir: str = "./storage/voices") -> str:
    if not path_or_url.startswith(("http://", "https://")):
        return path_or_url
    import hashlib, urllib.request
    os.makedirs(storage_dir, exist_ok=True)
    url_hash = hashlib.md5(path_or_url.encode()).hexdigest()[:12]
    ext = os.path.splitext(path_or_url.split("?")[0])[1] or ".wav"
    local_path = os.path.join(storage_dir, f"dl_{url_hash}{ext}")
    if os.path.exists(local_path):
        return local_path
    logger.info("Downloading ref audio: %s", path_or_url)
    urllib.request.urlretrieve(path_or_url, local_path)
    return local_path
