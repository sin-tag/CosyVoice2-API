"""
Shared Voice Cache management system
Allows multiple TTS engines (CosyVoice2, CosyVoice3, Chatterbox) to share voice samples
"""

import json
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from enum import Enum

from app.models.voice import VoiceInDB, VoiceCreate, VoiceUpdate, VoiceType, VoiceStats
from app.core.config import settings

import logging
logger = logging.getLogger(__name__)


class TTSEngine(str, Enum):
    """Supported TTS engines"""
    COSYVOICE2 = "cosyvoice2"
    COSYVOICE3 = "cosyvoice3"
    CHATTERBOX = "chatterbox"
    ALL = "all"  # Compatible with all engines


class SharedVoiceCache:
    """
    Shared voice cache that allows multiple TTS engines to use the same voice samples.

    Features:
    - Single database for all voices
    - Engine compatibility tracking (which engines can use which voice)
    - Cross-engine voice sharing
    - Lazy loading of engine-specific model data
    """

    def __init__(self, cache_dir: str, db_file: str = None):
        self.cache_dir = Path(cache_dir)
        self.db_file = Path(db_file or os.path.join(cache_dir, "shared_voices.json"))
        self.voices: Dict[str, VoiceInDB] = {}
        self.voice_engines: Dict[str, Set[str]] = {}  # voice_id -> set of compatible engines
        self._lock = asyncio.Lock()

        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize the shared voice cache by loading from disk"""
        async with self._lock:
            await self._load_from_disk()
            await self._migrate_from_separate_caches()
            logger.info(f"SharedVoiceCache initialized with {len(self.voices)} voices")

    async def _migrate_from_separate_caches(self):
        """Migrate voices from separate cache files to shared cache"""
        cache_files = [
            ("voices.json", TTSEngine.COSYVOICE2),
            ("voices_v3.json", TTSEngine.COSYVOICE3),
            ("voices_chatterbox.json", TTSEngine.CHATTERBOX),
        ]

        migrated = 0
        for filename, engine in cache_files:
            cache_path = self.cache_dir / filename
            if cache_path.exists():
                try:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    for voice_id, voice_data in data.items():
                        if voice_id not in self.voices:
                            # Convert and add to shared cache
                            try:
                                if 'created_at' in voice_data:
                                    voice_data['created_at'] = datetime.fromisoformat(voice_data['created_at'])
                                if 'updated_at' in voice_data:
                                    voice_data['updated_at'] = datetime.fromisoformat(voice_data['updated_at'])

                                voice = VoiceInDB(**voice_data)
                                self.voices[voice_id] = voice
                                self.voice_engines[voice_id] = {engine.value, TTSEngine.CHATTERBOX.value}
                                migrated += 1
                                logger.info(f"Migrated voice '{voice_id}' from {filename}")
                            except Exception as e:
                                logger.warning(f"Failed to migrate voice {voice_id}: {e}")
                        else:
                            # Voice already exists, just add engine compatibility
                            if voice_id not in self.voice_engines:
                                self.voice_engines[voice_id] = set()
                            self.voice_engines[voice_id].add(engine.value)

                except Exception as e:
                    logger.warning(f"Failed to migrate from {filename}: {e}")

        if migrated > 0:
            await self._save_to_disk()
            logger.info(f"Migrated {migrated} voices to shared cache")

    async def _load_from_disk(self):
        """Load voice cache from disk"""
        if not self.db_file.exists():
            self.voices = {}
            self.voice_engines = {}
            return

        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.voices = {}
            self.voice_engines = {}

            voices_data = data.get('voices', data)  # Support both old and new format
            engines_data = data.get('engines', {})

            for voice_id, voice_data in voices_data.items():
                try:
                    if 'created_at' in voice_data:
                        voice_data['created_at'] = datetime.fromisoformat(voice_data['created_at'])
                    if 'updated_at' in voice_data:
                        voice_data['updated_at'] = datetime.fromisoformat(voice_data['updated_at'])

                    # Handle model_data conversion
                    if 'model_data' in voice_data and voice_data['model_data']:
                        import torch
                        import numpy as np
                        model_data = voice_data['model_data']
                        tensor_model_data = {}
                        for key, value in model_data.items():
                            if isinstance(value, dict) and 'data' in value:
                                data_array = np.array(value['data'])
                                dtype_str = value.get('dtype', 'torch.float32')
                                if 'float32' in dtype_str:
                                    dtype = torch.float32
                                elif 'float64' in dtype_str:
                                    dtype = torch.float64
                                elif 'int32' in dtype_str:
                                    dtype = torch.int32
                                elif 'int64' in dtype_str:
                                    dtype = torch.int64
                                else:
                                    dtype = torch.float32
                                tensor_model_data[key] = torch.tensor(data_array, dtype=dtype)
                            elif isinstance(value, list):
                                tensor_model_data[key] = torch.tensor(np.array(value), dtype=torch.float32)
                            else:
                                tensor_model_data[key] = value
                        voice_data['model_data'] = tensor_model_data

                    voice = VoiceInDB(**voice_data)
                    self.voices[voice_id] = voice

                    # Load engine compatibility
                    if voice_id in engines_data:
                        self.voice_engines[voice_id] = set(engines_data[voice_id])
                    else:
                        # Default: compatible with all engines (audio file based)
                        self.voice_engines[voice_id] = {TTSEngine.CHATTERBOX.value}

                except Exception as e:
                    logger.warning(f"Failed to load voice {voice_id}: {e}")

        except Exception as e:
            logger.warning(f"Failed to load shared voice cache: {e}")
            self.voices = {}
            self.voice_engines = {}

    async def _save_to_disk(self):
        """Save voice cache to disk"""
        try:
            voices_data = {}
            for voice_id, voice in self.voices.items():
                voice_dict = voice.dict()
                if 'created_at' in voice_dict:
                    voice_dict['created_at'] = voice_dict['created_at'].isoformat()
                if 'updated_at' in voice_dict:
                    voice_dict['updated_at'] = voice_dict['updated_at'].isoformat()

                # Handle model_data with tensors
                if 'model_data' in voice_dict and voice_dict['model_data']:
                    model_data = voice_dict['model_data']
                    serializable_model_data = {}
                    for key, value in model_data.items():
                        if hasattr(value, 'cpu') and hasattr(value, 'numpy'):
                            tensor_cpu = value.cpu()
                            serializable_model_data[key] = {
                                'data': tensor_cpu.numpy().tolist(),
                                'dtype': str(tensor_cpu.dtype),
                                'shape': list(tensor_cpu.shape)
                            }
                        elif hasattr(value, 'tolist'):
                            serializable_model_data[key] = {
                                'data': value.tolist(),
                                'dtype': str(value.dtype),
                                'shape': list(value.shape)
                            }
                        else:
                            serializable_model_data[key] = value
                    voice_dict['model_data'] = serializable_model_data

                voices_data[voice_id] = voice_dict

            # Convert engines sets to lists for JSON
            engines_data = {
                voice_id: list(engines)
                for voice_id, engines in self.voice_engines.items()
            }

            data = {
                'voices': voices_data,
                'engines': engines_data,
                'version': '2.0',
                'updated_at': datetime.utcnow().isoformat()
            }

            temp_file = self.db_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            temp_file.replace(self.db_file)

        except Exception as e:
            logger.error(f"Failed to save shared voice cache: {e}")
            raise

    async def add_voice(
        self,
        voice_create: VoiceCreate,
        audio_file_path: str,
        model_data: Optional[Dict[str, Any]] = None,
        file_size: Optional[int] = None,
        duration: Optional[float] = None,
        sample_rate: Optional[int] = None,
        compatible_engines: Optional[List[str]] = None
    ) -> VoiceInDB:
        """Add a new voice to the shared cache"""
        async with self._lock:
            if voice_create.voice_id in self.voices:
                raise ValueError(f"Voice with ID '{voice_create.voice_id}' already exists")

            now = datetime.utcnow()
            voice = VoiceInDB(
                **voice_create.dict(),
                created_at=now,
                updated_at=now,
                audio_file_path=audio_file_path,
                model_data=model_data,
                file_size=file_size,
                duration=duration,
                sample_rate=sample_rate
            )

            self.voices[voice_create.voice_id] = voice

            # Set engine compatibility - Chatterbox can use any voice with audio file
            if compatible_engines:
                self.voice_engines[voice_create.voice_id] = set(compatible_engines)
            else:
                # Default: Chatterbox can always use audio-based voices
                self.voice_engines[voice_create.voice_id] = {TTSEngine.CHATTERBOX.value}

            await self._save_to_disk()
            return voice

    async def get_voice(self, voice_id: str) -> Optional[VoiceInDB]:
        """Get a voice by ID"""
        return self.voices.get(voice_id)

    async def get_voice_for_engine(self, voice_id: str, engine: str) -> Optional[VoiceInDB]:
        """Get a voice if it's compatible with the specified engine"""
        voice = self.voices.get(voice_id)
        if voice and voice.audio_file_path:
            # Chatterbox can use any voice that has an audio file
            if engine == TTSEngine.CHATTERBOX.value:
                return voice
            # Other engines need explicit compatibility
            if voice_id in self.voice_engines and engine in self.voice_engines[voice_id]:
                return voice
        return None

    async def list_voices(
        self,
        voice_type: Optional[VoiceType] = None,
        language: Optional[str] = None,
        engine: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> tuple[List[VoiceInDB], int]:
        """List voices with optional filtering and pagination"""
        voices = list(self.voices.values())

        # Apply filters
        if voice_type:
            voices = [v for v in voices if v.voice_type == voice_type]
        if language:
            voices = [v for v in voices if v.language == language]
        if engine:
            if engine == TTSEngine.CHATTERBOX.value:
                # Chatterbox can use any voice with audio file
                voices = [v for v in voices if v.audio_file_path]
            else:
                # Other engines need explicit compatibility
                voices = [
                    v for v in voices
                    if v.voice_id in self.voice_engines
                    and engine in self.voice_engines[v.voice_id]
                ]

        total = len(voices)

        # Sort by updated_at descending
        voices.sort(key=lambda v: v.updated_at, reverse=True)

        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        voices = voices[start:end]

        return voices, total

    async def update_voice(self, voice_id: str, voice_update: VoiceUpdate) -> Optional[VoiceInDB]:
        """Update a voice's information"""
        async with self._lock:
            voice = self.voices.get(voice_id)
            if not voice:
                return None

            update_data = voice_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(voice, field, value)

            voice.updated_at = datetime.utcnow()
            await self._save_to_disk()
            return voice

    async def update_voice_model_data(self, voice_id: str, model_data: Dict[str, Any]) -> Optional[VoiceInDB]:
        """Update the model data for a voice"""
        async with self._lock:
            voice = self.voices.get(voice_id)
            if not voice:
                return None

            voice.model_data = model_data
            voice.updated_at = datetime.utcnow()
            await self._save_to_disk()
            return voice

    async def add_engine_compatibility(self, voice_id: str, engine: str) -> bool:
        """Add engine compatibility to a voice"""
        async with self._lock:
            if voice_id not in self.voices:
                return False

            if voice_id not in self.voice_engines:
                self.voice_engines[voice_id] = set()

            self.voice_engines[voice_id].add(engine)
            await self._save_to_disk()
            return True

    async def remove_engine_compatibility(self, voice_id: str, engine: str) -> bool:
        """Remove engine compatibility from a voice"""
        async with self._lock:
            if voice_id not in self.voice_engines:
                return False

            self.voice_engines[voice_id].discard(engine)
            await self._save_to_disk()
            return True

    async def get_compatible_engines(self, voice_id: str) -> List[str]:
        """Get list of engines compatible with a voice"""
        voice = self.voices.get(voice_id)
        if not voice:
            return []

        engines = list(self.voice_engines.get(voice_id, set()))

        # Chatterbox is always compatible if voice has audio file
        if voice.audio_file_path and TTSEngine.CHATTERBOX.value not in engines:
            engines.append(TTSEngine.CHATTERBOX.value)

        return engines

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a voice from the cache"""
        async with self._lock:
            voice = self.voices.get(voice_id)
            if not voice:
                return False

            # Remove audio file if it exists
            if voice.audio_file_path and os.path.exists(voice.audio_file_path):
                try:
                    os.remove(voice.audio_file_path)
                except Exception as e:
                    logger.warning(f"Failed to remove audio file {voice.audio_file_path}: {e}")

            # Remove from caches
            del self.voices[voice_id]
            if voice_id in self.voice_engines:
                del self.voice_engines[voice_id]

            await self._save_to_disk()
            return True

    async def get_stats(self, engine: Optional[str] = None) -> VoiceStats:
        """Get voice cache statistics"""
        if engine:
            voices, _ = await self.list_voices(engine=engine, page_size=10000)
        else:
            voices = list(self.voices.values())

        total_voices = len(voices)

        by_type = {}
        for voice_type in VoiceType:
            by_type[voice_type] = len([v for v in voices if v.voice_type == voice_type])

        by_language = {}
        for voice in voices:
            if voice.language:
                by_language[voice.language] = by_language.get(voice.language, 0) + 1

        total_storage_size = sum(v.file_size or 0 for v in voices)

        durations = [v.duration for v in voices if v.duration is not None]
        average_duration = sum(durations) / len(durations) if durations else None

        return VoiceStats(
            total_voices=total_voices,
            by_type=by_type,
            by_language=by_language,
            total_storage_size=total_storage_size,
            average_duration=average_duration
        )

    async def voice_exists(self, voice_id: str) -> bool:
        """Check if a voice exists in the cache"""
        return voice_id in self.voices

    async def get_all_voice_ids(self, engine: Optional[str] = None) -> List[str]:
        """Get all voice IDs in the cache, optionally filtered by engine"""
        if engine:
            voices, _ = await self.list_voices(engine=engine, page_size=10000)
            return [v.voice_id for v in voices]
        return list(self.voices.keys())


# Global shared cache instance
_shared_cache: Optional[SharedVoiceCache] = None


def get_shared_voice_cache() -> SharedVoiceCache:
    """Get the global shared voice cache instance"""
    global _shared_cache
    if _shared_cache is None:
        _shared_cache = SharedVoiceCache(
            cache_dir=settings.VOICE_CACHE_DIR,
            db_file=os.path.join(settings.VOICE_CACHE_DIR, "shared_voices.json")
        )
    return _shared_cache


async def initialize_shared_cache():
    """Initialize the global shared voice cache"""
    cache = get_shared_voice_cache()
    await cache.initialize()
    return cache
