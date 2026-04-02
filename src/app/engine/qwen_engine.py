import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from app.engine.base import TTSEngine

logger = logging.getLogger(__name__)

# Qwen3-TTS uses full language names
QWEN_LANGUAGES = ["Chinese", "English", "Japanese", "Korean", "German", "French", "Russian", "Portuguese", "Spanish", "Italian"]

# ISO code → Qwen language name mapping
QWEN_LANG_MAP = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "ru": "Russian",
    "pt": "Portuguese",
    "es": "Spanish",
    "it": "Italian",
}

QWEN_LANG_CODES = list(QWEN_LANG_MAP.keys())


class QwenEngine(TTSEngine):
    """Adapter for Qwen/Qwen3-TTS-12Hz-0.6B-Base.

    0.6B params, 10 languages, 97ms latency, voice cloning with 3s minimum reference.
    Uses dffdeeq/Qwen3-TTS-streaming fork for streaming capability.
    """

    name = "qwen"
    supported_languages = QWEN_LANG_CODES

    def __init__(self, model_path: str, device: str = "cuda:1", dtype: str = "bfloat16"):
        self._model_path = model_path
        self._device = device
        self._dtype = dtype
        self._model = None
        self._streaming_available = False

    def _resolve_language(self, language: str) -> str:
        """Convert ISO code to Qwen language name."""
        if language in QWEN_LANG_MAP:
            return QWEN_LANG_MAP[language]
        if language in QWEN_LANGUAGES:
            return language
        raise ValueError(f"Unsupported language: {language}")

    async def load_model(self) -> None:
        logger.info("Loading Qwen3-TTS model from %s on %s...", self._model_path, self._device)

        def _load():
            import torch

            dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
            torch_dtype = dtype_map.get(self._dtype, torch.bfloat16)

            # Try streaming fork first, fallback to official package
            try:
                from qwen_tts_streaming import Qwen3TTSModel

                model = Qwen3TTSModel.from_pretrained(
                    self._model_path,
                    device_map=self._device,
                    dtype=torch_dtype,
                    attn_implementation="sdpa",
                )
                return model, True
            except ImportError:
                logger.info("Streaming fork not available, using official qwen-tts package")

            from qwen_tts import Qwen3TTSModel

            model = Qwen3TTSModel.from_pretrained(
                self._model_path,
                device_map=self._device,
                dtype=torch_dtype,
                attn_implementation="sdpa",
            )
            return model, False

        self._model, self._streaming_available = await asyncio.to_thread(_load)
        logger.info("Qwen3-TTS loaded (streaming=%s)", self._streaming_available)

    async def unload_model(self) -> None:
        if self._model is not None:
            import torch

            del self._model
            self._model = None
            torch.cuda.empty_cache()
            logger.info("Qwen3-TTS unloaded")

    def is_loaded(self) -> bool:
        return self._model is not None

    async def generate(
        self,
        text: str,
        language: str,
        voice_data: Any | None = None,
        **params,
    ) -> tuple[np.ndarray, int]:
        lang_name = self._resolve_language(language)

        def _generate():
            if voice_data is None:
                raise ValueError("Qwen3-TTS Base model requires a reference voice (voice_id). Upload a voice first via POST /api/v1/voices")
            ref_text = voice_data.get("ref_text", "")
            clone_kwargs = {
                "text": text,
                "language": lang_name,
                "ref_audio": voice_data["ref_audio"],
            }
            if ref_text:
                clone_kwargs["ref_text"] = ref_text
            else:
                clone_kwargs["x_vector_only_mode"] = True
            wavs, sr = self._model.generate_voice_clone(**clone_kwargs)

            audio = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            if audio.ndim > 1:
                audio = audio.squeeze()

            return audio.astype(np.float32), sr

        return await asyncio.to_thread(_generate)

    async def stream_generate(
        self,
        text: str,
        language: str,
        voice_data: Any | None = None,
        **params,
    ) -> AsyncIterator[np.ndarray]:
        lang_name = self._resolve_language(language)

        if not self._streaming_available:
            # Fallback: generate full audio and yield as single chunk
            audio, sr = await self.generate(text, language, voice_data, **params)
            yield audio
            return

        queue: asyncio.Queue[np.ndarray | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _stream():
            try:
                stream_kwargs = {
                    "text": text,
                    "language": lang_name,
                }
                if voice_data is not None:
                    stream_kwargs["ref_audio"] = voice_data["ref_audio"]
                    stream_kwargs["ref_text"] = voice_data.get("ref_text", "")
                    gen = self._model.stream_generate_voice_clone(**stream_kwargs)
                else:
                    gen = self._model.stream_generate_pcm(**stream_kwargs)

                for chunk in gen:
                    if hasattr(chunk, "cpu"):
                        chunk = chunk.cpu().numpy()
                    if chunk.ndim > 1:
                        chunk = chunk.squeeze()
                    loop.call_soon_threadsafe(queue.put_nowait, chunk.astype(np.float32))
            except Exception as e:
                logger.error("Qwen streaming error: %s", e, exc_info=True)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _stream)

        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    async def generate_dialogue(
        self,
        segments: list[dict],
        speaker_refs: dict[str, str],
        language: str = "en",
        speaker_ref_texts: dict[str, str] | None = None,
        **params,
    ) -> tuple[np.ndarray, int]:
        """Generate multi-speaker dialogue by running each segment individually then concatenating.

        Args:
            segments: [{"speaker": "narrator", "text": "..."}, ...]
            speaker_refs: {"narrator": "/path/to/ref.wav", ...}
            speaker_ref_texts: {"narrator": "text spoken in ref audio", ...} (optional)
            language: ISO code
        """
        speaker_ref_texts = speaker_ref_texts or {}
        lang_name = self._resolve_language(language)

        def _generate_all():
            audio_parts = []
            sr = 24000

            for seg in segments:
                ref_path = speaker_refs.get(seg["speaker"])
                if not ref_path:
                    logger.warning("No ref audio for speaker '%s', skipping", seg["speaker"])
                    continue

                ref_text = speaker_ref_texts.get(seg["speaker"], "")
                clone_kwargs = {
                    "text": seg["text"],
                    "language": lang_name,
                    "ref_audio": ref_path,
                }
                if ref_text:
                    clone_kwargs["ref_text"] = ref_text
                else:
                    clone_kwargs["x_vector_only_mode"] = True
                wavs, sr = self._model.generate_voice_clone(**clone_kwargs)

                audio = wavs[0] if isinstance(wavs, (list, tuple)) else wavs
                if hasattr(audio, "cpu"):
                    audio = audio.cpu().numpy()
                if audio.ndim > 1:
                    audio = audio.squeeze()
                audio_parts.append(audio.astype(np.float32))

                # Small silence between segments (0.3s)
                silence = np.zeros(int(sr * 0.3), dtype=np.float32)
                audio_parts.append(silence)

            if not audio_parts:
                raise RuntimeError("No audio segments generated")

            # Remove trailing silence
            audio_parts = audio_parts[:-1]
            return np.concatenate(audio_parts), sr

        return await asyncio.to_thread(_generate_all)

    async def prepare_voice(self, audio_path: str, reference_text: str | None = None) -> Any:
        """For Qwen, voice data includes reference audio path and text."""
        return {
            "ref_audio": audio_path,
            "ref_text": reference_text or "",
        }

    async def load_cached_voice(self, cache_path: str) -> Any:
        def _load():
            import torch
            return torch.load(cache_path, map_location="cpu", weights_only=False)
        return await asyncio.to_thread(_load)

    async def save_voice_cache(self, voice_data: Any, cache_path: str) -> None:
        def _save():
            import torch
            torch.save(voice_data, cache_path)
        await asyncio.to_thread(_save)
