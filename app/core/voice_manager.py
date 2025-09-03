"""
Voice manager for CosyVoice2 API
Handles CosyVoice model initialization and voice management
"""

import os
import sys
import asyncio
import logging
from typing import Optional, Dict, Any, List, Generator
from pathlib import Path

# Add CosyVoice to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if f'{ROOT_DIR}/third_party/Matcha-TTS' not in sys.path:
    sys.path.insert(0, f'{ROOT_DIR}/third_party/Matcha-TTS')

from cosyvoice.cli.cosyvoice import CosyVoice, CosyVoice2
from cosyvoice.utils.file_utils import load_wav

from app.core.voice_cache import VoiceCache
from app.core.config import settings
from app.models.voice import VoiceInDB, VoiceCreate, VoiceUpdate, VoiceType
from app.utils.audio import audio_processor
from app.utils.file_utils import file_manager

logger = logging.getLogger(__name__)


class VoiceManager:
    """Main voice manager class"""
    
    def __init__(self, model_dir: str, cache_dir: str):
        self.model_dir = model_dir
        self.cache_dir = cache_dir
        self.voice_cache = VoiceCache(cache_dir, settings.VOICE_CACHE_DB)
        self.cosyvoice_model: Optional[CosyVoice] = None
        self.cosyvoice2_model: Optional[CosyVoice2] = None
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize the voice manager"""
        async with self._lock:
            if self._initialized:
                return
            
            logger.info("Initializing voice manager...")
            
            try:
                # Initialize voice cache
                await self.voice_cache.initialize()
                logger.info("Voice cache initialized")
                
                # Initialize CosyVoice models
                await self._initialize_models()
                logger.info("CosyVoice models initialized")
                
                # Load cached voices into models
                await self._load_cached_voices()
                logger.info("Cached voices loaded")
                
                self._initialized = True
                logger.info("Voice manager initialization complete")
                
            except Exception as e:
                logger.error(f"Failed to initialize voice manager: {e}")
                raise
    
    async def _initialize_models(self):
        """Initialize CosyVoice models"""
        try:
            # Check if model directory exists
            if not os.path.exists(self.model_dir):
                raise ValueError(f"Model directory not found: {self.model_dir}")
            
            # Initialize models in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Try to initialize CosyVoice2 first, fallback to CosyVoice
            try:
                self.cosyvoice2_model = await loop.run_in_executor(
                    None, self._init_cosyvoice2_sync
                )
                logger.info("CosyVoice2 model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load CosyVoice2 model: {e}")
                
                # Fallback to CosyVoice
                try:
                    self.cosyvoice_model = await loop.run_in_executor(
                        None, self._init_cosyvoice_sync
                    )
                    logger.info("CosyVoice model loaded successfully")
                except Exception as e2:
                    logger.error(f"Failed to load CosyVoice model: {e2}")
                    raise ValueError("Failed to load any CosyVoice model")
                    
        except Exception as e:
            logger.error(f"Error initializing models: {e}")
            raise
    
    def _init_cosyvoice2_sync(self) -> CosyVoice2:
        """Synchronously initialize CosyVoice2 model"""
        return CosyVoice2(self.model_dir)
    
    def _init_cosyvoice_sync(self) -> CosyVoice:
        """Synchronously initialize CosyVoice model"""
        return CosyVoice(self.model_dir)
    
    async def _load_cached_voices(self):
        """Load cached voices into the model"""
        try:
            voices, _ = await self.voice_cache.list_voices()
            
            for voice in voices:
                if voice.voice_type in [VoiceType.ZERO_SHOT, VoiceType.CROSS_LINGUAL]:
                    if voice.model_data and voice.audio_file_path:
                        try:
                            # Add voice to model's speaker info
                            model = self._get_active_model()
                            if model and hasattr(model, 'frontend'):
                                model.frontend.spk2info[voice.voice_id] = voice.model_data
                                logger.info(f"Loaded cached voice: {voice.voice_id}")
                        except Exception as e:
                            logger.warning(f"Failed to load cached voice {voice.voice_id}: {e}")
                            
        except Exception as e:
            logger.error(f"Error loading cached voices: {e}")
    
    def _get_active_model(self) -> Optional[CosyVoice]:
        """Get the active CosyVoice model"""
        return self.cosyvoice2_model or self.cosyvoice_model
    
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
            
            # Generate model data for zero-shot voices
            model_data = None
            if voice_create.voice_type in [VoiceType.ZERO_SHOT, VoiceType.CROSS_LINGUAL]:
                model_data = await self._generate_voice_model_data(
                    target_path, voice_create.prompt_text or ""
                )
            
            # Add to cache
            voice = await self.voice_cache.add_voice(
                voice_create=voice_create,
                audio_file_path=target_path,
                model_data=model_data,
                file_size=file_manager.get_file_size(target_path),
                duration=duration,
                sample_rate=sample_rate
            )
            
            # Add to active model if it's a zero-shot voice
            if model_data and voice_create.voice_type in [VoiceType.ZERO_SHOT, VoiceType.CROSS_LINGUAL]:
                model = self._get_active_model()
                if model and hasattr(model, 'frontend'):
                    model.frontend.spk2info[voice_create.voice_id] = model_data
            
            logger.info(f"Successfully added voice: {voice_create.voice_id}")
            return voice
            
        except Exception as e:
            logger.error(f"Error adding voice {voice_create.voice_id}: {e}")
            raise
    
    async def _generate_voice_model_data(self, audio_path: str, prompt_text: str) -> Optional[Dict[str, Any]]:
        """Generate model data for a voice"""
        try:
            model = self._get_active_model()
            if not model or not hasattr(model, 'frontend'):
                return None
            
            # Load audio
            loop = asyncio.get_event_loop()
            prompt_speech_16k = await loop.run_in_executor(
                None, load_wav, audio_path, 16000
            )
            
            # Generate model input
            model_input = model.frontend.frontend_zero_shot(
                '', prompt_text, prompt_speech_16k, model.sample_rate, ''
            )
            
            # Remove text-related fields to get speaker embedding
            if 'text' in model_input:
                del model_input['text']
            if 'text_len' in model_input:
                del model_input['text_len']
            
            return model_input
            
        except Exception as e:
            logger.error(f"Error generating voice model data: {e}")
            return None
    
    async def get_voice(self, voice_id: str) -> Optional[VoiceInDB]:
        """Get a voice by ID"""
        return await self.voice_cache.get_voice(voice_id)
    
    async def list_voices(self, **kwargs) -> tuple[List[VoiceInDB], int]:
        """List voices with filtering and pagination"""
        return await self.voice_cache.list_voices(**kwargs)
    
    async def update_voice(self, voice_id: str, voice_update: VoiceUpdate) -> Optional[VoiceInDB]:
        """Update a voice's information"""
        return await self.voice_cache.update_voice(voice_id, voice_update)
    
    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a voice from the cache"""
        # Remove from active model
        model = self._get_active_model()
        if model and hasattr(model, 'frontend') and voice_id in model.frontend.spk2info:
            del model.frontend.spk2info[voice_id]
        
        # Remove from cache
        return await self.voice_cache.delete_voice(voice_id)
    
    async def get_available_pretrained_voices(self) -> List[str]:
        """Get list of available pre-trained voices"""
        model = self._get_active_model()
        if model and hasattr(model, 'list_available_spks'):
            return model.list_available_spks()
        return []
    
    def is_ready(self) -> bool:
        """Check if voice manager is ready"""
        return self._initialized and (self.cosyvoice_model is not None or self.cosyvoice2_model is not None)
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up voice manager...")
        await audio_processor.cleanup()
        logger.info("Voice manager cleanup complete")
