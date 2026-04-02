import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import numpy as np

from app.engine.base import TTSEngine

logger = logging.getLogger(__name__)

MOSS_LANGUAGES = [
    "zh", "ja", "ko", "fa", "ar", "en", "de", "es", "fr", "it",
    "pl", "pt", "cs", "da", "sv", "hu", "el", "tr", "ru", "he",
]


class MossEngine(TTSEngine):
    """Adapter for OpenMOSS-Team/MOSS-TTS-Realtime.

    1.7B params, 20 languages, native streaming, requires ~15GB VRAM.
    """

    name = "moss"
    supported_languages = MOSS_LANGUAGES

    def __init__(self, model_path: str, codec_path: str, device: str = "cuda:0", dtype: str = "bfloat16"):
        self._model_path = model_path
        self._codec_path = codec_path
        self._device = device
        self._dtype = dtype
        self._model = None
        self._inferencer = None

    async def load_model(self) -> None:
        logger.info("Loading MOSS-TTS-Realtime model from %s on %s...", self._model_path, self._device)

        def _load():
            import torch
            from transformers import AutoModel, AutoTokenizer

            dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
            torch_dtype = dtype_map.get(self._dtype, torch.bfloat16)

            tokenizer = AutoTokenizer.from_pretrained(self._model_path, trust_remote_code=True)
            model = AutoModel.from_pretrained(
                self._model_path,
                torch_dtype=torch_dtype,
                device_map=self._device,
                trust_remote_code=True,
            )
            model.eval()

            # Load codec for audio reconstruction
            codec = AutoModel.from_pretrained(
                self._codec_path,
                torch_dtype=torch_dtype,
                trust_remote_code=True,
            ).to(self._device)
            codec.eval()

            return model, tokenizer, codec

        self._model, self._tokenizer, self._codec = await asyncio.to_thread(_load)
        logger.info("MOSS-TTS-Realtime loaded successfully")

    async def unload_model(self) -> None:
        if self._model is not None:
            import torch

            del self._model
            del self._tokenizer
            del self._codec
            self._model = None
            self._tokenizer = None
            self._codec = None
            self._inferencer = None
            torch.cuda.empty_cache()
            logger.info("MOSS-TTS-Realtime unloaded")

    def is_loaded(self) -> bool:
        return self._model is not None

    async def generate(
        self,
        text: str,
        language: str,
        voice_data: Any | None = None,
        **params,
    ) -> tuple[np.ndarray, int]:
        def _generate():
            import torch

            generate_kwargs = {
                "text": text,
                "language": language,
                "temperature": params.get("temperature", 0.7),
                "top_p": params.get("top_p", 0.9),
                "top_k": params.get("top_k", 50),
                "repetition_penalty": params.get("repetition_penalty", 1.2),
            }

            if voice_data is not None:
                generate_kwargs["reference_audio_path"] = voice_data.get("reference_audio_path")

            with torch.no_grad():
                result = self._model.generate(**generate_kwargs)

            if isinstance(result, tuple):
                audio = result[0]
                sr = result[1] if len(result) > 1 else 24000
            else:
                audio = result
                sr = 24000

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
        import torch

        queue: asyncio.Queue[np.ndarray | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _stream():
            generate_kwargs = {
                "text": text,
                "language": language,
                "temperature": params.get("temperature", 0.7),
                "top_p": params.get("top_p", 0.9),
                "top_k": params.get("top_k", 50),
                "repetition_penalty": params.get("repetition_penalty", 1.2),
            }

            if voice_data is not None:
                generate_kwargs["reference_audio_path"] = voice_data.get("reference_audio_path")

            try:
                with torch.no_grad():
                    for chunk in self._model.stream_generate(**generate_kwargs):
                        if hasattr(chunk, "cpu"):
                            chunk = chunk.cpu().numpy()
                        if chunk.ndim > 1:
                            chunk = chunk.squeeze()
                        loop.call_soon_threadsafe(queue.put_nowait, chunk.astype(np.float32))
            except Exception as e:
                logger.error("MOSS streaming error: %s", e, exc_info=True)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        loop.run_in_executor(None, _stream)

        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    async def prepare_voice(self, audio_path: str, reference_text: str | None = None) -> Any:
        """For MOSS, voice data is simply the reference audio path. The model handles embedding internally."""
        return {"reference_audio_path": audio_path}

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
