"""
FastAPI dependencies for dependency injection
"""

from typing import Optional
from fastapi import HTTPException

from app.core.synthesis_engine import SynthesisEngine
from app.core.voice_manager import VoiceManager

# Global instances (will be set during startup)
_synthesis_engine: Optional[SynthesisEngine] = None
_voice_manager: Optional[VoiceManager] = None

def set_synthesis_engine(engine: SynthesisEngine):
    """Set the global synthesis engine instance"""
    global _synthesis_engine
    _synthesis_engine = engine

def set_voice_manager(manager: VoiceManager):
    """Set the global voice manager instance"""
    global _voice_manager
    _voice_manager = manager

def get_synthesis_engine() -> SynthesisEngine:
    """Get the synthesis engine dependency"""
    if _synthesis_engine is None:
        raise HTTPException(status_code=503, detail="Synthesis engine not ready")
    return _synthesis_engine

def get_voice_manager() -> VoiceManager:
    """Get the voice manager dependency"""
    if _voice_manager is None:
        raise HTTPException(status_code=503, detail="Voice manager not ready")
    return _voice_manager
