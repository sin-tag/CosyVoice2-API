"""
Tests for voice cache functionality
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from app.core.voice_cache import VoiceCache
from app.models.voice import VoiceCreate, VoiceUpdate, VoiceType, AudioFormat


@pytest.fixture
async def voice_cache():
    """Create a temporary voice cache for testing"""
    temp_dir = tempfile.mkdtemp()
    cache_dir = Path(temp_dir) / "cache"
    db_file = Path(temp_dir) / "voices.json"
    
    cache = VoiceCache(str(cache_dir), str(db_file))
    await cache.initialize()
    
    yield cache
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_add_voice(voice_cache):
    """Test adding a voice to cache"""
    voice_create = VoiceCreate(
        voice_id="test_voice_001",
        name="Test Voice",
        description="A test voice",
        voice_type=VoiceType.ZERO_SHOT,
        language="en",
        prompt_text="Hello world",
        audio_format=AudioFormat.WAV
    )
    
    voice = await voice_cache.add_voice(
        voice_create=voice_create,
        audio_file_path="/fake/path/test.wav",
        file_size=1024,
        duration=2.5,
        sample_rate=22050
    )
    
    assert voice.voice_id == "test_voice_001"
    assert voice.name == "Test Voice"
    assert voice.voice_type == VoiceType.ZERO_SHOT
    assert voice.file_size == 1024
    assert voice.duration == 2.5


@pytest.mark.asyncio
async def test_get_voice(voice_cache):
    """Test getting a voice from cache"""
    # Add a voice first
    voice_create = VoiceCreate(
        voice_id="test_voice_002",
        name="Test Voice 2",
        voice_type=VoiceType.PRETRAINED,
        audio_format=AudioFormat.WAV
    )
    
    await voice_cache.add_voice(
        voice_create=voice_create,
        audio_file_path="/fake/path/test2.wav"
    )
    
    # Get the voice
    voice = await voice_cache.get_voice("test_voice_002")
    assert voice is not None
    assert voice.voice_id == "test_voice_002"
    assert voice.name == "Test Voice 2"
    
    # Try to get non-existent voice
    voice = await voice_cache.get_voice("non_existent")
    assert voice is None


@pytest.mark.asyncio
async def test_list_voices(voice_cache):
    """Test listing voices with filtering"""
    # Add multiple voices
    voices_data = [
        ("voice_001", "Voice 1", VoiceType.ZERO_SHOT, "en"),
        ("voice_002", "Voice 2", VoiceType.PRETRAINED, "en"),
        ("voice_003", "Voice 3", VoiceType.ZERO_SHOT, "zh"),
    ]
    
    for voice_id, name, voice_type, language in voices_data:
        voice_create = VoiceCreate(
            voice_id=voice_id,
            name=name,
            voice_type=voice_type,
            language=language,
            audio_format=AudioFormat.WAV
        )
        await voice_cache.add_voice(
            voice_create=voice_create,
            audio_file_path=f"/fake/path/{voice_id}.wav"
        )
    
    # List all voices
    voices, total = await voice_cache.list_voices()
    assert total == 3
    assert len(voices) == 3
    
    # Filter by voice type
    voices, total = await voice_cache.list_voices(voice_type=VoiceType.ZERO_SHOT)
    assert total == 2
    assert len(voices) == 2
    
    # Filter by language
    voices, total = await voice_cache.list_voices(language="en")
    assert total == 2
    assert len(voices) == 2


@pytest.mark.asyncio
async def test_update_voice(voice_cache):
    """Test updating a voice"""
    # Add a voice first
    voice_create = VoiceCreate(
        voice_id="test_voice_update",
        name="Original Name",
        description="Original description",
        voice_type=VoiceType.ZERO_SHOT,
        audio_format=AudioFormat.WAV
    )
    
    await voice_cache.add_voice(
        voice_create=voice_create,
        audio_file_path="/fake/path/test.wav"
    )
    
    # Update the voice
    voice_update = VoiceUpdate(
        name="Updated Name",
        description="Updated description"
    )
    
    updated_voice = await voice_cache.update_voice("test_voice_update", voice_update)
    assert updated_voice is not None
    assert updated_voice.name == "Updated Name"
    assert updated_voice.description == "Updated description"
    assert updated_voice.voice_id == "test_voice_update"  # Should not change


@pytest.mark.asyncio
async def test_delete_voice(voice_cache):
    """Test deleting a voice"""
    # Add a voice first
    voice_create = VoiceCreate(
        voice_id="test_voice_delete",
        name="To Delete",
        voice_type=VoiceType.ZERO_SHOT,
        audio_format=AudioFormat.WAV
    )
    
    await voice_cache.add_voice(
        voice_create=voice_create,
        audio_file_path="/fake/path/test.wav"
    )
    
    # Verify it exists
    voice = await voice_cache.get_voice("test_voice_delete")
    assert voice is not None
    
    # Delete it
    success = await voice_cache.delete_voice("test_voice_delete")
    assert success is True
    
    # Verify it's gone
    voice = await voice_cache.get_voice("test_voice_delete")
    assert voice is None
    
    # Try to delete non-existent voice
    success = await voice_cache.delete_voice("non_existent")
    assert success is False


@pytest.mark.asyncio
async def test_voice_exists(voice_cache):
    """Test checking if voice exists"""
    # Should not exist initially
    exists = await voice_cache.voice_exists("test_exists")
    assert exists is False
    
    # Add a voice
    voice_create = VoiceCreate(
        voice_id="test_exists",
        name="Exists Test",
        voice_type=VoiceType.ZERO_SHOT,
        audio_format=AudioFormat.WAV
    )
    
    await voice_cache.add_voice(
        voice_create=voice_create,
        audio_file_path="/fake/path/test.wav"
    )
    
    # Should exist now
    exists = await voice_cache.voice_exists("test_exists")
    assert exists is True
