"""
Voice cache management system for CosyVoice2 API
"""

import json
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    from app.models.voice import VoiceInDB, VoiceCreate, VoiceUpdate, VoiceType, VoiceStats
    from app.core.config import settings
except ImportError:
    # Fallback for relative imports
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from app.models.voice import VoiceInDB, VoiceCreate, VoiceUpdate, VoiceType, VoiceStats
    from app.core.config import settings


class VoiceCache:
    """Voice cache management system"""
    
    def __init__(self, cache_dir: str, db_file: str):
        self.cache_dir = Path(cache_dir)
        self.db_file = Path(db_file)
        self.voices: Dict[str, VoiceInDB] = {}
        self._lock = asyncio.Lock()
        
        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self):
        """Initialize the voice cache by loading from disk"""
        async with self._lock:
            await self._load_from_disk()
    
    async def _load_from_disk(self):
        """Load voice cache from disk"""
        if not self.db_file.exists():
            self.voices = {}
            return
        
        try:
            with open(self.db_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.voices = {}
            for voice_id, voice_data in data.items():
                try:
                    # Convert datetime strings back to datetime objects
                    if 'created_at' in voice_data:
                        voice_data['created_at'] = datetime.fromisoformat(voice_data['created_at'])
                    if 'updated_at' in voice_data:
                        voice_data['updated_at'] = datetime.fromisoformat(voice_data['updated_at'])
                    
                    voice = VoiceInDB(**voice_data)
                    self.voices[voice_id] = voice
                except Exception as e:
                    print(f"Warning: Failed to load voice {voice_id}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Warning: Failed to load voice cache: {e}")
            self.voices = {}
    
    async def _save_to_disk(self):
        """Save voice cache to disk"""
        try:
            # Convert to serializable format
            data = {}
            for voice_id, voice in self.voices.items():
                voice_dict = voice.dict()
                # Convert datetime objects to ISO strings
                if 'created_at' in voice_dict:
                    voice_dict['created_at'] = voice_dict['created_at'].isoformat()
                if 'updated_at' in voice_dict:
                    voice_dict['updated_at'] = voice_dict['updated_at'].isoformat()
                data[voice_id] = voice_dict
            
            # Write to temporary file first, then rename for atomic operation
            temp_file = self.db_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            temp_file.replace(self.db_file)
            
        except Exception as e:
            print(f"Error: Failed to save voice cache: {e}")
            raise
    
    async def add_voice(self, voice_create: VoiceCreate, audio_file_path: str, 
                       model_data: Optional[Dict[str, Any]] = None,
                       file_size: Optional[int] = None,
                       duration: Optional[float] = None,
                       sample_rate: Optional[int] = None) -> VoiceInDB:
        """Add a new voice to the cache"""
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
            await self._save_to_disk()
            return voice
    
    async def get_voice(self, voice_id: str) -> Optional[VoiceInDB]:
        """Get a voice by ID"""
        return self.voices.get(voice_id)
    
    async def list_voices(self, voice_type: Optional[VoiceType] = None,
                         language: Optional[str] = None,
                         page: int = 1, page_size: int = 50) -> tuple[List[VoiceInDB], int]:
        """List voices with optional filtering and pagination"""
        voices = list(self.voices.values())
        
        # Apply filters
        if voice_type:
            voices = [v for v in voices if v.voice_type == voice_type]
        if language:
            voices = [v for v in voices if v.language == language]
        
        total = len(voices)
        
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
            
            # Update fields
            update_data = voice_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(voice, field, value)
            
            voice.updated_at = datetime.utcnow()
            await self._save_to_disk()
            return voice
    
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
                    print(f"Warning: Failed to remove audio file {voice.audio_file_path}: {e}")
            
            # Remove from cache
            del self.voices[voice_id]
            await self._save_to_disk()
            return True
    
    async def get_stats(self) -> VoiceStats:
        """Get voice cache statistics"""
        voices = list(self.voices.values())
        total_voices = len(voices)
        
        # Count by type
        by_type = {}
        for voice_type in VoiceType:
            by_type[voice_type] = len([v for v in voices if v.voice_type == voice_type])
        
        # Count by language
        by_language = {}
        for voice in voices:
            if voice.language:
                by_language[voice.language] = by_language.get(voice.language, 0) + 1
        
        # Calculate storage size
        total_storage_size = sum(v.file_size or 0 for v in voices)
        
        # Calculate average duration
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
    
    async def get_all_voice_ids(self) -> List[str]:
        """Get all voice IDs in the cache"""
        return list(self.voices.keys())
