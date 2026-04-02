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
    """Adapter for OpenMOSS-Team/MOSS-TTSD-v1.0.

    8B params, 20 languages, up to 5 speakers, designed for dialogue/dubbing.
    Uses speaker tags [S1]..[S5] to control voices in multi-speaker generation.
    """

    name = "moss"
    supported_languages = MOSS_LANGUAGES

    def __init__(self, model_path: str, device: str = "cuda:0", dtype: str = "bfloat16", **kwargs):
        self._model_path = model_path
        self._device = device
        self._dtype = dtype
        self._model = None
        self._processor = None

    async def load_model(self) -> None:
        logger.info("Loading MOSS-TTSD model from %s on %s...", self._model_path, self._device)

        def _load():
            import torch
            from transformers import AutoModel, AutoProcessor

            # Required: disable cuDNN SDPA backend for MOSS-TTSD
            torch.backends.cuda.enable_cudnn_sdp(False)

            dtype_map = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}
            torch_dtype = dtype_map.get(self._dtype, torch.bfloat16)

            processor = AutoProcessor.from_pretrained(self._model_path, trust_remote_code=True)
            model = AutoModel.from_pretrained(
                self._model_path,
                torch_dtype=torch_dtype,
                device_map=self._device,
                trust_remote_code=True,
            )
            model.eval()

            # Move audio tokenizer to device
            if hasattr(processor, "audio_tokenizer"):
                processor.audio_tokenizer = processor.audio_tokenizer.to(self._device)

            return model, processor

        self._model, self._processor = await asyncio.to_thread(_load)
        logger.info("MOSS-TTSD loaded on %s", self._device)

    async def unload_model(self) -> None:
        if self._model is not None:
            import torch
            del self._model
            del self._processor
            self._model = None
            self._processor = None
            torch.cuda.empty_cache()
            logger.info("MOSS-TTSD unloaded from %s", self._device)

    def is_loaded(self) -> bool:
        return self._model is not None

    def _encode_reference(self, audio_path: str) -> Any:
        """Encode a reference audio file into audio codes for MOSS-TTSD."""
        import torch
        import torchaudio

        wav, sr = torchaudio.load(audio_path)
        target_sr = self._processor.model_config.sampling_rate
        if sr != target_sr:
            wav = torchaudio.functional.resample(wav, sr, target_sr)
        # Ensure mono
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)

        codes = self._processor.encode_audios_from_wav([wav], sampling_rate=target_sr)
        return codes

    async def generate_dialogue(
        self,
        segments: list[dict],
        speaker_refs: dict[str, str],
        language: str = "en",
        **params,
    ) -> tuple[np.ndarray, int]:
        """Generate multi-speaker dialogue audio.

        Args:
            segments: [{"speaker": "narrator", "text": "..."}, {"speaker": "char1", "text": "..."}, ...]
            speaker_refs: {"narrator": "/path/to/ref.wav", "char1": "/path/to/ref.wav", ...}
            language: language code
            **params: temperature, top_p, top_k, repetition_penalty, max_new_tokens

        Returns:
            (audio_array, sample_rate)
        """
        def _generate():
            import torch

            # Map speaker names to [S1], [S2], ...
            speaker_names = list(dict.fromkeys(seg["speaker"] for seg in segments))
            speaker_map = {name: f"[S{i+1}]" for i, name in enumerate(speaker_names)}

            # Build tagged text: [S1] narrator line\n[S2] char1 line\n...
            tagged_lines = []
            for seg in segments:
                tag = speaker_map[seg["speaker"]]
                tagged_lines.append(f"{tag} {seg['text']}")
            full_text = "\n".join(tagged_lines)

            # Encode reference audios in speaker order
            ref_codes_list = []
            for name in speaker_names:
                audio_path = speaker_refs.get(name)
                if audio_path:
                    codes = self._encode_reference(audio_path)
                    ref_codes_list.append(codes)
                else:
                    logger.warning("No reference audio for speaker '%s', using empty", name)
                    ref_codes_list.append(None)

            # Filter out None refs — pack only valid ones
            valid_refs = [c for c in ref_codes_list if c is not None]

            # Build conversation
            user_msg = self._processor.build_user_message(
                text=full_text,
                reference=valid_refs if valid_refs else None,
            )
            conversations = [user_msg]

            # Tokenize
            inputs = self._processor(conversations, mode="continuation")
            input_ids = inputs["input_ids"].to(self._device)
            attention_mask = inputs["attention_mask"].to(self._device)

            # Generate
            max_tokens = params.get("max_new_tokens", 2000)
            with torch.no_grad():
                outputs = self._model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    max_new_tokens=max_tokens,
                    audio_temperature=params.get("temperature", 1.1),
                    audio_top_p=params.get("top_p", 0.9),
                    audio_top_k=params.get("top_k", 50),
                    audio_repetition_penalty=params.get("repetition_penalty", 1.1),
                )

            # Decode
            messages = self._processor.decode(outputs)

            # Extract audio from the last assistant message
            for msg in reversed(messages):
                if hasattr(msg, "audio_codes_list") and msg.audio_codes_list:
                    audio = msg.audio_codes_list[0]
                    if hasattr(audio, "cpu"):
                        audio = audio.cpu().numpy()
                    if audio.ndim > 1:
                        audio = audio.squeeze()
                    sr = self._processor.model_config.sampling_rate
                    return audio.astype(np.float32), sr

            raise RuntimeError("MOSS-TTSD returned no audio output")

        return await asyncio.to_thread(_generate)

    # ──── Standard TTSEngine interface (single speaker) ────

    async def generate(
        self,
        text: str,
        language: str,
        voice_data: Any | None = None,
        **params,
    ) -> tuple[np.ndarray, int]:
        """Single-speaker generation via dialogue API with one speaker."""
        ref_path = voice_data.get("reference_audio_path") if voice_data else None
        segments = [{"speaker": "speaker", "text": text}]
        speaker_refs = {"speaker": ref_path} if ref_path else {}
        return await self.generate_dialogue(segments, speaker_refs, language, **params)

    async def stream_generate(
        self,
        text: str,
        language: str,
        voice_data: Any | None = None,
        **params,
    ) -> AsyncIterator[np.ndarray]:
        """MOSS-TTSD is not a streaming model — generate full audio then yield as single chunk."""
        audio, sr = await self.generate(text, language, voice_data, **params)
        yield audio

    async def prepare_voice(self, audio_path: str, reference_text: str | None = None) -> Any:
        """Voice data is simply the reference audio path — MOSS-TTSD handles encoding internally."""
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
