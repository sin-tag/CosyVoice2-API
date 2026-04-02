from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

import numpy as np


class TTSEngine(ABC):
    """Abstract base class for TTS engine adapters."""

    name: str
    supported_languages: list[str]

    @abstractmethod
    async def load_model(self) -> None:
        """Load the model onto the GPU."""

    @abstractmethod
    async def unload_model(self) -> None:
        """Unload the model and free GPU memory."""

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""

    @abstractmethod
    async def generate(
        self,
        text: str,
        language: str,
        voice_data: Any | None = None,
        **params,
    ) -> tuple[np.ndarray, int]:
        """Synchronous generation. Returns (audio_array, sample_rate)."""

    @abstractmethod
    async def stream_generate(
        self,
        text: str,
        language: str,
        voice_data: Any | None = None,
        **params,
    ) -> AsyncIterator[np.ndarray]:
        """Streaming generation. Yields audio chunks as numpy arrays."""

    @abstractmethod
    async def prepare_voice(self, audio_path: str, reference_text: str | None = None) -> Any:
        """Pre-compute speaker embedding from reference audio. Returns cacheable data."""

    @abstractmethod
    async def load_cached_voice(self, cache_path: str) -> Any:
        """Load a previously cached speaker embedding from disk."""

    @abstractmethod
    async def save_voice_cache(self, voice_data: Any, cache_path: str) -> None:
        """Save speaker embedding to disk for persistence."""

    def supports_language(self, language: str) -> bool:
        return language in self.supported_languages
