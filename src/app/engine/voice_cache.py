import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.base import TTSEngine
from app.models.voice import Voice

logger = logging.getLogger(__name__)


class VoiceCache:
    """Three-tier voice embedding cache: Memory -> Disk -> DB (re-compute).

    - Tier 1: In-memory dict[str, Any] -- sub-millisecond lookup
    - Tier 2: .pt files on disk -- loaded via engine.load_cached_voice()
    - Tier 3: DB reference audio -- engine.prepare_voice() computes embedding from scratch
    """

    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {
            "moss": {},
            "qwen": {},
        }

    async def warm_from_db(self, db: AsyncSession, engine: TTSEngine) -> int:
        """Load all cached voice embeddings from disk into memory on startup."""
        engine_name = engine.name
        cache_col = Voice.moss_cached_data if engine_name == "moss" else Voice.qwen_cached_data

        result = await db.execute(select(Voice).where(cache_col.isnot(None)))
        voices = result.scalars().all()

        count = 0
        for voice in voices:
            cache_path = voice.moss_cached_data if engine_name == "moss" else voice.qwen_cached_data
            if not cache_path:
                continue
            try:
                voice_data = await engine.load_cached_voice(cache_path)
                self._cache[engine_name][voice.id] = voice_data
                count += 1
            except Exception:
                logger.warning("Failed to load cached voice %s for engine %s", voice.id, engine_name, exc_info=True)

        logger.info("Warmed %d voices for engine '%s'", count, engine_name)
        return count

    async def get_or_prepare(
        self,
        voice_id: uuid.UUID,
        engine: TTSEngine,
        db: AsyncSession,
    ) -> Any:
        """Get voice data from cache, or prepare and cache it."""
        engine_name = engine.name
        vid = str(voice_id)

        # Tier 1: Memory
        if vid in self._cache[engine_name]:
            return self._cache[engine_name][vid]

        # Load voice record from DB
        voice = await db.get(Voice, vid)
        if voice is None:
            return None

        cache_path = voice.moss_cached_data if engine_name == "moss" else voice.qwen_cached_data

        # Tier 2: Disk
        if cache_path:
            try:
                voice_data = await engine.load_cached_voice(cache_path)
                self._cache[engine_name][vid] = voice_data
                return voice_data
            except Exception:
                logger.warning("Disk cache miss for voice %s engine %s, recomputing", vid, engine_name)

        # Tier 3: Compute from reference audio
        voice_data = await engine.prepare_voice(voice.reference_audio_path, voice.reference_text)

        # Persist to disk + DB
        from app.core.config import settings

        cache_file = f"{settings.voices_storage_path}/{vid}_{engine_name}.pt"
        await engine.save_voice_cache(voice_data, cache_file)

        if engine_name == "moss":
            voice.moss_cached_data = cache_file
        else:
            voice.qwen_cached_data = cache_file
        await db.commit()

        # Populate memory cache
        self._cache[engine_name][vid] = voice_data
        logger.info("Computed and cached voice %s for engine '%s'", vid, engine_name)

        return voice_data

    def add(self, voice_id: uuid.UUID | str, engine_name: str, voice_data: Any) -> None:
        """Add a pre-computed voice embedding to the in-memory cache."""
        self._cache[engine_name][str(voice_id)] = voice_data

    def remove(self, voice_id: uuid.UUID | str) -> None:
        """Remove a voice from all engine caches."""
        vid = str(voice_id)
        for engine_cache in self._cache.values():
            engine_cache.pop(vid, None)

    def get_cached_count(self, engine_name: str) -> int:
        return len(self._cache.get(engine_name, {}))


# Singleton
voice_cache = VoiceCache()
