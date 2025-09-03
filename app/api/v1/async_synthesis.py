"""
Async voice synthesis API endpoints
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from app.models.synthesis import (
    SFTSynthesisRequest, ZeroShotSynthesisRequest, 
    CrossLingualSynthesisRequest, InstructSynthesisRequest,
    SynthesisResponse, AudioFormat
)
from app.core.voice_manager import VoiceManager
from app.core.async_synthesis import AsyncSynthesisManager, TaskStatus
from app.core.exceptions import (
    SynthesisError, VoiceNotFoundError, ModelNotReadyError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/async", tags=["Async Voice Synthesis"])


def get_voice_manager(request: Request) -> VoiceManager:
    """Dependency to get voice manager from app state"""
    voice_manager = getattr(request.app.state, 'voice_manager', None)
    if not voice_manager:
        raise HTTPException(status_code=503, detail="Voice manager not available")
    if not voice_manager.is_ready():
        raise ModelNotReadyError("Voice manager is not ready")
    return voice_manager


def get_async_synthesis_manager(request: Request) -> AsyncSynthesisManager:
    """Dependency to get async synthesis manager from app state"""
    async_manager = getattr(request.app.state, 'async_synthesis_manager', None)
    if not async_manager:
        raise HTTPException(status_code=503, detail="Async synthesis manager not available")
    return async_manager


@router.post("/synthesize/sft")
async def async_synthesize_sft(
    request: SFTSynthesisRequest,
    async_manager: AsyncSynthesisManager = Depends(get_async_synthesis_manager)
):
    """Submit SFT synthesis task (async)"""
    
    try:
        task_id = await async_manager.submit_sft_task(request)
        
        return {
            "task_id": task_id,
            "status": "submitted",
            "message": "SFT synthesis task submitted successfully",
            "check_status_url": f"/api/v1/async/tasks/{task_id}/status",
            "result_url": f"/api/v1/async/tasks/{task_id}/result"
        }
        
    except Exception as e:
        logger.error(f"Error submitting SFT synthesis task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize/zero-shot")
async def async_synthesize_zero_shot(
    text: str = Form(..., description="Text to synthesize"),
    speed: float = Form(1.0, description="Synthesis speed", ge=0.5, le=2.0),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    stream: bool = Form(False, description="Enable streaming synthesis"),
    voice_id: Optional[str] = Form(None, description="Cached voice ID (if using cached voice)"),
    prompt_text: Optional[str] = Form(None, description="Text that matches the prompt audio"),
    prompt_audio: Optional[UploadFile] = File(None, description="Prompt audio file for voice cloning"),
    async_manager: AsyncSynthesisManager = Depends(get_async_synthesis_manager)
):
    """Submit zero-shot synthesis task (async)"""
    
    try:
        # Validate inputs
        if not voice_id and not prompt_audio:
            raise HTTPException(
                status_code=400, 
                detail="Either voice_id or prompt_audio must be provided"
            )
        
        if not voice_id and not prompt_text:
            raise HTTPException(
                status_code=400,
                detail="prompt_text is required when using prompt_audio"
            )
        
        # Create request object
        request = ZeroShotSynthesisRequest(
            text=text,
            speed=speed,
            format=format,
            stream=stream,
            voice_id=voice_id,
            prompt_text=prompt_text
        )
        
        # Read prompt audio if provided
        prompt_audio_content = None
        if prompt_audio:
            prompt_audio_content = await prompt_audio.read()
            if len(prompt_audio_content) == 0:
                raise HTTPException(status_code=400, detail="Empty audio file")
        
        task_id = await async_manager.submit_zero_shot_task(request, prompt_audio_content)
        
        return {
            "task_id": task_id,
            "status": "submitted",
            "message": "Zero-shot synthesis task submitted successfully",
            "check_status_url": f"/api/v1/async/tasks/{task_id}/status",
            "result_url": f"/api/v1/async/tasks/{task_id}/result"
        }
        
    except Exception as e:
        logger.error(f"Error submitting zero-shot synthesis task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize/cross-lingual")
async def async_synthesize_cross_lingual(
    text: str = Form(..., description="Text to synthesize"),
    speed: float = Form(1.0, description="Synthesis speed", ge=0.5, le=2.0),
    format: AudioFormat = Form(AudioFormat.WAV, description="Output audio format"),
    stream: bool = Form(False, description="Enable streaming synthesis"),
    voice_id: Optional[str] = Form(None, description="Cached voice ID (if using cached voice)"),
    prompt_audio: Optional[UploadFile] = File(None, description="Prompt audio file for voice cloning"),
    async_manager: AsyncSynthesisManager = Depends(get_async_synthesis_manager)
):
    """Submit cross-lingual synthesis task (async)"""
    
    try:
        # Validate inputs
        if not voice_id and not prompt_audio:
            raise HTTPException(
                status_code=400, 
                detail="Either voice_id or prompt_audio must be provided"
            )
        
        # Create request object
        request = CrossLingualSynthesisRequest(
            text=text,
            speed=speed,
            format=format,
            stream=stream,
            voice_id=voice_id
        )
        
        # Read prompt audio if provided
        prompt_audio_content = None
        if prompt_audio:
            prompt_audio_content = await prompt_audio.read()
            if len(prompt_audio_content) == 0:
                raise HTTPException(status_code=400, detail="Empty audio file")
        
        task_id = await async_manager.submit_cross_lingual_task(request, prompt_audio_content)
        
        return {
            "task_id": task_id,
            "status": "submitted",
            "message": "Cross-lingual synthesis task submitted successfully",
            "check_status_url": f"/api/v1/async/tasks/{task_id}/status",
            "result_url": f"/api/v1/async/tasks/{task_id}/result"
        }
        
    except Exception as e:
        logger.error(f"Error submitting cross-lingual synthesis task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize/instruct")
async def async_synthesize_instruct(
    request: InstructSynthesisRequest,
    async_manager: AsyncSynthesisManager = Depends(get_async_synthesis_manager)
):
    """Submit instruct synthesis task (async)"""
    
    try:
        task_id = await async_manager.submit_instruct_task(request)
        
        return {
            "task_id": task_id,
            "status": "submitted",
            "message": "Instruct synthesis task submitted successfully",
            "check_status_url": f"/api/v1/async/tasks/{task_id}/status",
            "result_url": f"/api/v1/async/tasks/{task_id}/result"
        }
        
    except Exception as e:
        logger.error(f"Error submitting instruct synthesis task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: str,
    async_manager: AsyncSynthesisManager = Depends(get_async_synthesis_manager)
):
    """Get synthesis task status"""
    
    try:
        task = await async_manager.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        response = {
            "task_id": task.task_id,
            "status": task.status.value,
            "progress": task.progress,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at
        }
        
        if task.error:
            response["error"] = task.error
        
        if task.status == TaskStatus.COMPLETED and task.result:
            response["result_available"] = True
            response["result_url"] = f"/api/v1/async/tasks/{task_id}/result"
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tasks/{task_id}/result")
async def get_task_result(
    task_id: str,
    async_manager: AsyncSynthesisManager = Depends(get_async_synthesis_manager)
):
    """Get synthesis task result"""
    
    try:
        task = await async_manager.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.status == TaskStatus.PENDING:
            raise HTTPException(status_code=202, detail="Task is still pending")
        elif task.status == TaskStatus.PROCESSING:
            raise HTTPException(status_code=202, detail="Task is still processing")
        elif task.status == TaskStatus.FAILED:
            raise HTTPException(status_code=500, detail=f"Task failed: {task.error}")
        elif task.status == TaskStatus.COMPLETED:
            if task.result:
                return task.result
            else:
                raise HTTPException(status_code=500, detail="Task completed but no result available")
        else:
            raise HTTPException(status_code=500, detail="Unknown task status")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task result {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    async_manager: AsyncSynthesisManager = Depends(get_async_synthesis_manager)
):
    """Cancel a synthesis task"""
    
    try:
        success = await async_manager.cancel_task(task_id)
        if success:
            return {"message": f"Task {task_id} cancelled successfully"}
        else:
            raise HTTPException(status_code=400, detail="Task cannot be cancelled (not pending)")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/tasks")
async def list_tasks(
    limit: int = 50,
    async_manager: AsyncSynthesisManager = Depends(get_async_synthesis_manager)
):
    """List recent synthesis tasks"""
    
    try:
        tasks = await async_manager.list_tasks(limit)
        
        return {
            "tasks": [
                {
                    "task_id": task.task_id,
                    "status": task.status.value,
                    "progress": task.progress,
                    "created_at": task.created_at,
                    "started_at": task.started_at,
                    "completed_at": task.completed_at,
                    "error": task.error
                }
                for task in tasks
            ],
            "total": len(tasks)
        }
        
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
