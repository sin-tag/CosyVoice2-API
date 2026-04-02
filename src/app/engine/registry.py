import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.engine.base import TTSEngine
from app.engine.voice_cache import voice_cache

logger = logging.getLogger(__name__)


class EngineRegistry:
    """Manages TTS engine lifecycle: load, get, shutdown, and GPU concurrency."""

    def __init__(self):
        self._engines: dict[str, TTSEngine] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._max_concurrent: int = 0

    async def initialize(self, config: Settings) -> None:
        """Load enabled engines sequentially (GPU memory must be allocated in order)."""
        gpu_concurrency = config.max_concurrent_generations
        self._max_concurrent = gpu_concurrency
        logger.info("GPU semaphore concurrency: %d", gpu_concurrency)

        if config.moss_enabled:
            from app.engine.moss_engine import MossEngine

            moss = MossEngine(
                model_path=config.moss_model_path,
                codec_path=config.moss_codec_path,
                device=config.moss_device,
                dtype=config.moss_dtype,
            )
            try:
                await moss.load_model()
                self._engines["moss"] = moss
                self._semaphores["moss"] = asyncio.Semaphore(gpu_concurrency)
                logger.info("MOSS engine registered")
            except Exception:
                logger.error("Failed to load MOSS engine", exc_info=True)

        if config.qwen_enabled:
            from app.engine.qwen_engine import QwenEngine

            qwen = QwenEngine(
                model_path=config.qwen_model_path,
                device=config.qwen_device,
                dtype=config.qwen_dtype,
            )
            try:
                await qwen.load_model()
                self._engines["qwen"] = qwen
                self._semaphores["qwen"] = asyncio.Semaphore(gpu_concurrency)
                logger.info("Qwen engine registered")
            except Exception:
                logger.error("Failed to load Qwen engine", exc_info=True)

        # Share semaphore if both engines on same GPU
        if config.moss_enabled and config.qwen_enabled and config.moss_device == config.qwen_device:
            shared = asyncio.Semaphore(gpu_concurrency)
            self._semaphores["moss"] = shared
            self._semaphores["qwen"] = shared
            logger.info("Shared GPU semaphore for MOSS and Qwen (same device: %s)", config.moss_device)

    async def warm_cache(self, db: AsyncSession) -> None:
        """Warm voice cache from DB for all loaded engines."""
        for engine in self._engines.values():
            await voice_cache.warm_from_db(db, engine)

    async def shutdown(self) -> None:
        """Unload all engines and free GPU memory."""
        for name, engine in self._engines.items():
            try:
                await engine.unload_model()
                logger.info("Engine '%s' unloaded", name)
            except Exception:
                logger.error("Error unloading engine '%s'", name, exc_info=True)
        self._engines.clear()
        self._semaphores.clear()

    def get(self, name: str) -> TTSEngine:
        engine = self._engines.get(name)
        if engine is None:
            from app.core.exceptions import EngineNotLoadedError

            raise EngineNotLoadedError(name)
        return engine

    def get_semaphore(self, name: str) -> asyncio.Semaphore:
        return self._semaphores[name]

    def gpu_slots(self, engine_name: str) -> dict:
        """Return free/total GPU generation slots for an engine."""
        sem = self._semaphores.get(engine_name)
        if sem is None:
            return {"free": 0, "total": 0}
        # Semaphore._value tracks available permits
        total = self._max_concurrent
        free = sem._value
        return {"free": free, "total": total, "busy": total - free}

    def all_gpu_slots(self) -> dict[str, dict]:
        """Return GPU slot info for all engines (deduped for shared semaphore)."""
        seen: dict[int, str] = {}
        result = {}
        for name in self._engines:
            sem = self._semaphores.get(name)
            if sem is None:
                continue
            sem_id = id(sem)
            if sem_id in seen:
                # Shared semaphore — reference the first engine's entry
                result[name] = result[seen[sem_id]]
            else:
                seen[sem_id] = name
                result[name] = self.gpu_slots(name)
        return result

    def list_engines(self) -> list[dict]:
        return [
            {
                "name": name,
                "loaded": engine.is_loaded(),
                "languages": engine.supported_languages,
                "cached_voices": voice_cache.get_cached_count(name),
                "gpu_slots": self.gpu_slots(name),
            }
            for name, engine in self._engines.items()
        ]

    @property
    def available_engines(self) -> list[str]:
        return list(self._engines.keys())


# Singleton
engine_registry = EngineRegistry()
