import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from app.engine.base import TTSEngine

logger = logging.getLogger(__name__)

# Max ref audio duration — auto-trim for speed
MAX_REF_AUDIO_SEC = 5

DEFAULT_REF_TEXT = "Hello, how are you today? Nice to meet you."


def _download_if_url(path_or_url: str, storage_dir: str = "./storage/voices") -> str:
    """If path_or_url is a URL, download to local storage. Otherwise return as-is."""
    if not path_or_url.startswith(("http://", "https://")):
        return path_or_url

    import hashlib
    import urllib.request

    os.makedirs(storage_dir, exist_ok=True)
    # Deterministic filename from URL
    url_hash = hashlib.md5(path_or_url.encode()).hexdigest()[:12]
    ext = os.path.splitext(path_or_url.split("?")[0])[1] or ".wav"
    local_path = os.path.join(storage_dir, f"dl_{url_hash}{ext}")

    if os.path.exists(local_path):
        return local_path

    logger.info("Downloading ref audio: %s", path_or_url)
    urllib.request.urlretrieve(path_or_url, local_path)
    logger.info("Saved to %s", local_path)
    return local_path


class OmniVoiceEngine(TTSEngine):
    """Adapter for k2-fsa/OmniVoice.

    600+ languages, zero-shot voice cloning + voice design, RTF ~0.025.
    Based on Qwen3-0.6B with diffusion, 24kHz output.
    """

    name = "omni"
    supported_languages = [
        "en", "zh", "ja", "ko", "de", "fr", "ru", "pt", "es", "it",
        "ar", "hi", "vi", "th", "pl", "nl", "sv", "da", "fi", "no",
    ]  # Top 20, but model supports 600+

    def __init__(self, model_path: str, device: str = "cuda:0", dtype: str = "float16"):
        self._model_path = model_path
        self._device = device
        self._dtype = dtype
        self._model = None

    async def load_model(self) -> None:
        logger.info("Loading OmniVoice from %s on %s...", self._model_path, self._device)

        def _load():
            import torch
            from omnivoice import OmniVoice

            dtype_map = {"float16": torch.float16, "bfloat16": torch.bfloat16, "float32": torch.float32}
            model = OmniVoice.from_pretrained(
                self._model_path,
                device_map=self._device,
                dtype=dtype_map.get(self._dtype, torch.float16),
            )
            return model

        self._model = await asyncio.to_thread(_load)
        logger.info("OmniVoice loaded on %s", self._device)

    async def unload_model(self) -> None:
        if self._model is not None:
            import torch
            del self._model
            self._model = None
            torch.cuda.empty_cache()

    def is_loaded(self) -> bool:
        return self._model is not None

    def _trim_ref_audio(self, audio_path: str) -> str:
        """Trim ref audio to MAX_REF_AUDIO_SEC if too long."""
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

    # ──── Generate ────

    async def generate(
        self, text: str, language: str, voice_data: Any | None = None, **params,
    ) -> tuple[np.ndarray, int]:
        if voice_data is None:
            raise ValueError("Voice required. Upload via POST /api/v1/voices first.")

        ref_audio = _download_if_url(voice_data["ref_audio"])
        ref_audio = self._trim_ref_audio(ref_audio)
        ref_text = voice_data.get("ref_text", "") or DEFAULT_REF_TEXT

        def _run():
            import torch
            with torch.inference_mode():
                audio_list = self._model.generate(
                    text=text,
                    ref_audio=ref_audio,
                    ref_text=ref_text,
                    language_id=language,
                )
            audio = audio_list[0]
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            return audio.squeeze().astype(np.float32), 24000

        return await asyncio.to_thread(_run)

    async def generate_with_design(
        self, text: str, instruct: str, language: str = "en", **params,
    ) -> tuple[np.ndarray, int]:
        """Generate speech with voice design (no reference audio needed)."""
        def _run():
            import torch
            with torch.inference_mode():
                audio_list = self._model.generate(
                    text=text,
                    instruct=instruct,
                    language_id=language,
                )
            audio = audio_list[0]
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            return audio.squeeze().astype(np.float32), 24000

        return await asyncio.to_thread(_run)

    async def generate_dialogue(
        self,
        segments: list[dict],
        speaker_refs: dict[str, str],
        language: str = "en",
        speaker_ref_texts: dict[str, str] | None = None,
        **params,
    ) -> tuple[np.ndarray, int]:
        """Generate each segment with voice clone, concatenate."""
        speaker_ref_texts = speaker_ref_texts or {}

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
                    ref_text = speaker_ref_texts.get(seg["speaker"], "") or DEFAULT_REF_TEXT

                    audio_list = self._model.generate(
                        text=seg["text"],
                        ref_audio=ref_path,
                        ref_text=ref_text,
                        language_id=language,
                    )

                    audio = audio_list[0]
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
        audio_path = _download_if_url(audio_path)
        return {"ref_audio": audio_path, "ref_text": reference_text or ""}

    async def load_cached_voice(self, cache_path: str) -> Any:
        import torch
        return await asyncio.to_thread(torch.load, cache_path, map_location="cpu", weights_only=False)

    async def save_voice_cache(self, voice_data: Any, cache_path: str) -> None:
        import torch
        await asyncio.to_thread(torch.save, voice_data, cache_path)
