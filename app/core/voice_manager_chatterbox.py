"""
Voice manager for Chatterbox TTS API
Handles Chatterbox model initialization and voice management
Uses SharedVoiceCache for cross-engine voice sharing
"""

import os
import sys
import asyncio
import logging
from typing import Optional, Dict, Any, List

from app.core.shared_voice_cache import SharedVoiceCache, TTSEngine, get_shared_voice_cache
from app.core.config import settings
from app.models.voice import VoiceInDB, VoiceCreate, VoiceUpdate, VoiceType
from app.utils.audio import audio_processor
from app.utils.file_utils import file_manager

logger = logging.getLogger(__name__)


class VoiceManagerChatterbox:
    """
    Voice manager for Chatterbox TTS

    Uses SharedVoiceCache to share voices with other TTS engines.
    Chatterbox can use any voice that has an audio file, regardless of which engine created it.
    """

    def __init__(self, model_dir: str, cache_dir: str, shared_cache: SharedVoiceCache = None):
        self.model_dir = model_dir
        self.cache_dir = cache_dir
        self.voice_cache = shared_cache or get_shared_voice_cache()
        self.chatterbox_model = None
        self.model_type = "multilingual"  # Default to multilingual model
        self._initialized = False
        self._lock = asyncio.Lock()
        self._engine = TTSEngine.CHATTERBOX.value

    async def initialize(self, model_type: str = "multilingual"):
        """
        Initialize the voice manager

        Args:
            model_type: One of "turbo", "multilingual", or "original"
        """
        async with self._lock:
            if self._initialized:
                return

            self.model_type = model_type
            logger.info(f"Initializing Chatterbox voice manager (model: {model_type})...")

            try:
                # Initialize shared voice cache (may already be initialized)
                await self.voice_cache.initialize()
                logger.info("Shared voice cache initialized for Chatterbox")

                # Initialize Chatterbox model
                await self._initialize_model()
                logger.info(f"Chatterbox {model_type} model initialized")

                # Load cached voices
                await self._load_cached_voices()
                logger.info("Cached voices loaded")

                self._initialized = True
                logger.info("Chatterbox voice manager initialization complete")

            except Exception as e:
                logger.error(f"Failed to initialize Chatterbox voice manager: {e}")
                raise

    async def _initialize_model(self):
        """Initialize Chatterbox model"""
        try:
            loop = asyncio.get_event_loop()
            self.chatterbox_model = await loop.run_in_executor(
                None, self._init_chatterbox_sync
            )
            logger.info(f"Chatterbox {self.model_type} model loaded successfully")
        except Exception as e:
            logger.error(f"Error initializing Chatterbox model: {e}")
            raise

    def _init_chatterbox_sync(self):
        """Synchronously initialize Chatterbox model"""
        try:
            import torch

            # Determine device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading Chatterbox on device: {device}")

            # Try to load the requested model type
            if self.model_type == "multilingual":
                try:
                    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
                    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
                    logger.info("Loaded ChatterboxMultilingualTTS model")
                    return model
                except ImportError:
                    logger.warning("ChatterboxMultilingualTTS not available, falling back to ChatterboxTTS")

            # Default: use ChatterboxTTS (English)
            from chatterbox.tts import ChatterboxTTS
            model = ChatterboxTTS.from_pretrained(device=device)
            logger.info("Loaded ChatterboxTTS model (English)")
            self.model_type = "original"  # Update to reflect actual loaded model
            return model

        except ImportError as e:
            logger.error(f"Chatterbox not installed: {e}")
            raise ImportError(
                "Chatterbox TTS not installed. Install with: pip install chatterbox-tts"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Chatterbox: {e}")
            raise

    async def _load_cached_voices(self):
        """Load cached voices"""
        try:
            voices, _ = await self.voice_cache.list_voices()
            logger.info(f"Loaded {len(voices)} cached Chatterbox voices")
        except Exception as e:
            logger.error(f"Error loading cached voices: {e}")

    def _get_active_model(self):
        """Get the active Chatterbox model"""
        return self.chatterbox_model

    def get_model_directly(self):
        """Get model directly - no locks for maximum parallelism"""
        return self._get_active_model()

    async def add_voice(self, voice_create: VoiceCreate, audio_file_content: bytes) -> VoiceInDB:
        """Add a new voice to the cache"""
        if not self._initialized:
            raise RuntimeError("Voice manager not initialized")

        # Validate voice doesn't already exist
        if await self.voice_cache.voice_exists(voice_create.voice_id):
            raise ValueError(f"Voice with ID '{voice_create.voice_id}' already exists")

        try:
            # Save audio file
            temp_file = await file_manager.save_temp_file(
                audio_file_content,
                f"{voice_create.voice_id}.{voice_create.audio_format.value}"
            )

            # Validate audio file
            is_valid, error_msg = await audio_processor.validate_audio_file(temp_file)
            if not is_valid:
                file_manager.delete_file(temp_file)
                raise ValueError(f"Invalid audio file: {error_msg}")

            # Get audio info
            audio_info = await audio_processor._get_audio_info(temp_file)
            duration, sample_rate, channels = audio_info if audio_info else (None, None, None)

            # Convert to target format if needed
            target_path = file_manager.get_voice_audio_path(
                voice_create.voice_id,
                voice_create.audio_format.value
            )

            # Ensure target directory exists
            file_manager.ensure_directory_exists(os.path.dirname(target_path))

            # Convert/copy audio file
            if voice_create.audio_format.value != "wav":
                success = await audio_processor.convert_audio_format(
                    temp_file, target_path, voice_create.audio_format
                )
                if not success:
                    file_manager.delete_file(temp_file)
                    raise ValueError("Failed to convert audio format")
            else:
                success = await file_manager.copy_file(temp_file, target_path)
                if not success:
                    file_manager.delete_file(temp_file)
                    raise ValueError("Failed to save audio file")

            # Clean up temp file
            file_manager.delete_file(temp_file)

            # Add to shared cache with Chatterbox compatibility
            voice = await self.voice_cache.add_voice(
                voice_create=voice_create,
                audio_file_path=target_path,
                model_data=None,  # Chatterbox extracts features at inference time
                file_size=file_manager.get_file_size(target_path),
                duration=duration,
                sample_rate=sample_rate,
                compatible_engines=[self._engine]  # Mark as Chatterbox compatible
            )

            logger.info(f"Successfully added Chatterbox voice: {voice_create.voice_id}")
            return voice

        except Exception as e:
            logger.error(f"Error adding voice {voice_create.voice_id}: {e}")
            raise

    async def get_voice(self, voice_id: str) -> Optional[VoiceInDB]:
        """Get a voice by ID (Chatterbox can use any voice with audio file)"""
        return await self.voice_cache.get_voice_for_engine(voice_id, self._engine)

    async def list_voices(self, **kwargs) -> tuple[List[VoiceInDB], int]:
        """List voices compatible with Chatterbox (all voices with audio files)"""
        return await self.voice_cache.list_voices(engine=self._engine, **kwargs)

    async def list_all_shared_voices(self, **kwargs) -> tuple[List[VoiceInDB], int]:
        """List all voices from shared cache (from all engines)"""
        return await self.voice_cache.list_voices(**kwargs)

    async def get_compatible_engines(self, voice_id: str) -> List[str]:
        """Get list of engines compatible with a voice"""
        return await self.voice_cache.get_compatible_engines(voice_id)

    async def update_voice(self, voice_id: str, voice_update: VoiceUpdate) -> Optional[VoiceInDB]:
        """Update a voice's information"""
        return await self.voice_cache.update_voice(voice_id, voice_update)

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a voice from the cache"""
        return await self.voice_cache.delete_voice(voice_id)

    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages based on model type"""
        if self.model_type == "multilingual":
            # Chatterbox-Multilingual supports 24+ languages
            return {
                "en": "English",
                "es": "Spanish",
                "fr": "French",
                "de": "German",
                "it": "Italian",
                "pt": "Portuguese",
                "pl": "Polish",
                "tr": "Turkish",
                "ru": "Russian",
                "nl": "Dutch",
                "cs": "Czech",
                "ar": "Arabic",
                "zh": "Chinese (Mandarin)",
                "ja": "Japanese",
                "hu": "Hungarian",
                "ko": "Korean",
                "hi": "Hindi",
                "vi": "Vietnamese",
                "uk": "Ukrainian",
                "el": "Greek",
                "ms": "Malay",
                "ro": "Romanian",
                "da": "Danish",
                "fi": "Finnish",
                "id": "Indonesian",
                "sv": "Swedish",
                "he": "Hebrew",
                "no": "Norwegian",
                "th": "Thai",
                "sk": "Slovak",
                "bg": "Bulgarian",
                "ca": "Catalan",
            }
        else:
            return {"en": "English"}  # Turbo and Original support English only

    def get_language_codes(self) -> List[str]:
        """Get list of supported language codes"""
        return list(self.get_supported_languages().keys())

    def is_ready(self) -> bool:
        """Check if voice manager is ready"""
        return self._initialized and self.chatterbox_model is not None

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up Chatterbox voice manager...")
        await audio_processor.cleanup()
        logger.info("Chatterbox voice manager cleanup complete")
