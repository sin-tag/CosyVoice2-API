from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


# ──── Standardized Error Response ────
# All errors follow: {"error": "<code>", "message": "<human-readable>", "details": {...}}


def error_response(status_code: int, error: str, message: str, **details) -> JSONResponse:
    body = {"error": error, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status_code, content=body)


# ──── Exception Handlers (register in main.py) ────


async def http_exception_handler(request: Request, exc: HTTPException):
    error_code = getattr(exc, "error_code", "http_error")
    return error_response(exc.status_code, error_code, exc.detail)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "Request validation failed",
        errors=exc.errors(),
    )


async def generic_exception_handler(request: Request, exc: Exception):
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "Internal server error",
    )


# ──── App Exceptions ────


class AppError(HTTPException):
    """Base exception with standardized error_code."""

    error_code: str = "app_error"

    def __init__(self, status_code: int, detail: str, error_code: str | None = None):
        super().__init__(status_code=status_code, detail=detail)
        if error_code:
            self.error_code = error_code


class EngineNotLoadedError(AppError):
    error_code = "engine_not_loaded"

    def __init__(self, engine: str):
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, f"Engine '{engine}' is not loaded")


class UnsupportedLanguageError(AppError):
    error_code = "unsupported_language"

    def __init__(self, language: str, engine: str, supported: list[str]):
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            f"Language '{language}' not supported by '{engine}'. Supported: {supported}",
        )


class VoiceNotFoundError(AppError):
    error_code = "voice_not_found"

    def __init__(self, voice_id: str):
        super().__init__(status.HTTP_404_NOT_FOUND, f"Voice '{voice_id}' not found")


class VoiceNotCompatibleError(AppError):
    error_code = "voice_not_compatible"

    def __init__(self, voice_id: str, engine: str):
        super().__init__(
            status.HTTP_400_BAD_REQUEST,
            f"Voice '{voice_id}' is not compatible with engine '{engine}'",
        )


class GenerationTimeoutError(AppError):
    error_code = "generation_timeout"

    def __init__(self):
        super().__init__(status.HTTP_504_GATEWAY_TIMEOUT, "Generation timed out")


class GPUOutOfMemoryError(AppError):
    error_code = "gpu_oom"

    def __init__(self):
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, "GPU out of memory. Try again later.")


class AudioProcessingError(AppError):
    error_code = "audio_processing_error"

    def __init__(self, detail: str = "Failed to process audio"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)
