"""
Exception handlers for CosyVoice2 API
"""

import logging
from typing import Union
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class VoiceManagerError(Exception):
    """Base exception for voice manager errors"""
    pass


class VoiceNotFoundError(VoiceManagerError):
    """Exception raised when a voice is not found"""
    pass


class VoiceAlreadyExistsError(VoiceManagerError):
    """Exception raised when trying to create a voice that already exists"""
    pass


class AudioProcessingError(VoiceManagerError):
    """Exception raised during audio processing"""
    pass


class ModelNotReadyError(VoiceManagerError):
    """Exception raised when CosyVoice model is not ready"""
    pass


class SynthesisError(VoiceManagerError):
    """Exception raised during voice synthesis"""
    pass


def setup_exception_handlers(app: FastAPI):
    """Setup exception handlers for the FastAPI app"""
    
    @app.exception_handler(VoiceNotFoundError)
    async def voice_not_found_handler(request: Request, exc: VoiceNotFoundError):
        logger.warning(f"Voice not found: {exc}")
        return JSONResponse(
            status_code=404,
            content={
                "error": "voice_not_found",
                "message": str(exc),
                "details": {"path": str(request.url)}
            }
        )
    
    @app.exception_handler(VoiceAlreadyExistsError)
    async def voice_already_exists_handler(request: Request, exc: VoiceAlreadyExistsError):
        logger.warning(f"Voice already exists: {exc}")
        return JSONResponse(
            status_code=409,
            content={
                "error": "voice_already_exists",
                "message": str(exc),
                "details": {"path": str(request.url)}
            }
        )
    
    @app.exception_handler(AudioProcessingError)
    async def audio_processing_error_handler(request: Request, exc: AudioProcessingError):
        logger.error(f"Audio processing error: {exc}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "audio_processing_error",
                "message": str(exc),
                "details": {"path": str(request.url)}
            }
        )
    
    @app.exception_handler(ModelNotReadyError)
    async def model_not_ready_handler(request: Request, exc: ModelNotReadyError):
        logger.error(f"Model not ready: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "model_not_ready",
                "message": str(exc),
                "details": {"path": str(request.url)}
            }
        )
    
    @app.exception_handler(SynthesisError)
    async def synthesis_error_handler(request: Request, exc: SynthesisError):
        logger.error(f"Synthesis error: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "synthesis_error",
                "message": str(exc),
                "details": {"path": str(request.url)}
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "Request validation failed",
                "details": {
                    "path": str(request.url),
                    "errors": exc.errors()
                }
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "http_error",
                "message": exc.detail,
                "details": {"path": str(request.url)}
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
                "details": {"path": str(request.url)}
            }
        )
