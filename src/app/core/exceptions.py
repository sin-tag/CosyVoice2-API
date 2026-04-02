from fastapi import HTTPException, status


class EngineNotLoadedError(HTTPException):
    def __init__(self, engine: str):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Engine '{engine}' is not loaded")


class UnsupportedLanguageError(HTTPException):
    def __init__(self, language: str, engine: str, supported: list[str]):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Language '{language}' not supported by '{engine}'. Supported: {supported}",
        )


class VoiceNotFoundError(HTTPException):
    def __init__(self, voice_id: str):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=f"Voice '{voice_id}' not found")


class VoiceNotCompatibleError(HTTPException):
    def __init__(self, voice_id: str, engine: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Voice '{voice_id}' is not compatible with engine '{engine}'",
        )


class GenerationTimeoutError(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Generation timed out")


class GPUOutOfMemoryError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GPU out of memory. Try again later.",
            headers={"Retry-After": "30"},
        )
