import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.engine.base import TTSEngine
from app.engine.voice_cache import voice_cache

logger = logging.getLogger(__name__)


class _EnginePool:
    """Pool of engine replicas across multiple GPUs with round-robin selection."""

    def __init__(self, name: str, replicas: list[TTSEngine], concurrency_per_gpu: int):
        self.name = name
        self.replicas = replicas
        self._semaphores = [asyncio.Semaphore(concurrency_per_gpu) for _ in replicas]
        self._concurrency_per_gpu = concurrency_per_gpu
        self._counter = 0  # round-robin counter

    def pick(self) -> tuple[TTSEngine, asyncio.Semaphore, int]:
        """Pick the least-busy GPU replica. Falls back to round-robin if all equal."""
        best_idx = 0
        best_free = -1
        for i, sem in enumerate(self._semaphores):
            free = sem._value
            if free > best_free:
                best_free = free
                best_idx = i
            # If all slots free on this GPU, pick it immediately
            if free == self._concurrency_per_gpu:
                break

        return self.replicas[best_idx], self._semaphores[best_idx], best_idx

    @property
    def first(self) -> TTSEngine:
        """Return first replica (for metadata like languages, name)."""
        return self.replicas[0]

    def total_slots(self) -> int:
        return self._concurrency_per_gpu * len(self.replicas)

    def free_slots(self) -> int:
        return sum(sem._value for sem in self._semaphores)

    def gpu_info(self) -> dict:
        total = self.total_slots()
        free = self.free_slots()
        return {
            "free": free,
            "total": total,
            "busy": total - free,
            "gpus": len(self.replicas),
            "per_gpu": [
                {"device": r._device if hasattr(r, '_device') else "?", "free": s._value, "total": self._concurrency_per_gpu}
                for r, s in zip(self.replicas, self._semaphores)
            ],
        }


class EngineRegistry:
    """Manages TTS engine lifecycle with multi-GPU support."""

    def __init__(self):
        self._pools: dict[str, _EnginePool] = {}
        self._max_concurrent: int = 0

    async def initialize(self, config: Settings) -> None:
        gpu_concurrency = config.max_concurrent_generations
        self._max_concurrent = gpu_concurrency
        logger.info("GPU semaphore concurrency per device: %d", gpu_concurrency)

        if config.omni_enabled:
            devices = [d.strip() for d in config.omni_device.split(",") if d.strip()]
            replicas = []
            for device in devices:
                from app.engine.omni_engine import OmniVoiceEngine
                engine = OmniVoiceEngine(
                    model_path=config.omni_model_path,
                    device=device,
                    dtype=config.omni_dtype,
                )
                try:
                    await engine.load_model()
                    replicas.append(engine)
                    logger.info("OmniVoice loaded on %s", device)
                except Exception:
                    logger.error("Failed to load OmniVoice on %s", device, exc_info=True)

            if replicas:
                self._pools["omni"] = _EnginePool("omni", replicas, gpu_concurrency)
                logger.info("OmniVoice registered: %d GPU(s)", len(replicas))

    async def warm_cache(self, db: AsyncSession) -> None:
        for pool in self._pools.values():
            # Warm cache using first replica
            await voice_cache.warm_from_db(db, pool.first)

    async def shutdown(self) -> None:
        for name, pool in self._pools.items():
            for i, engine in enumerate(pool.replicas):
                try:
                    await engine.unload_model()
                    logger.info("Engine '%s' replica %d unloaded", name, i)
                except Exception:
                    logger.error("Error unloading '%s' replica %d", name, i, exc_info=True)
        self._pools.clear()

    def get(self, name: str) -> TTSEngine:
        """Get first replica (for metadata). Use pick() for generation."""
        pool = self._pools.get(name)
        if pool is None:
            from app.core.exceptions import EngineNotLoadedError
            raise EngineNotLoadedError(name)
        return pool.first

    def pick(self, name: str) -> tuple[TTSEngine, asyncio.Semaphore, int]:
        """Pick the least-busy GPU replica for generation."""
        pool = self._pools.get(name)
        if pool is None:
            from app.core.exceptions import EngineNotLoadedError
            raise EngineNotLoadedError(name)
        return pool.pick()

    def get_semaphore(self, name: str) -> asyncio.Semaphore:
        """Backward compat — returns semaphore of least-busy replica."""
        _, sem, _ = self.pick(name)
        return sem

    def gpu_slots(self, engine_name: str) -> dict:
        pool = self._pools.get(engine_name)
        if pool is None:
            return {"free": 0, "total": 0, "busy": 0, "gpus": 0, "per_gpu": []}
        return pool.gpu_info()

    def all_gpu_slots(self) -> dict[str, dict]:
        return {name: pool.gpu_info() for name, pool in self._pools.items()}

    def list_engines(self) -> list[dict]:
        return [
            {
                "name": name,
                "loaded": pool.first.is_loaded(),
                "languages": pool.first.supported_languages,
                "cached_voices": voice_cache.get_cached_count(name),
                "gpu_slots": pool.gpu_info(),
            }
            for name, pool in self._pools.items()
        ]

    @property
    def available_engines(self) -> list[str]:
        return list(self._pools.keys())


# Singleton
engine_registry = EngineRegistry()
