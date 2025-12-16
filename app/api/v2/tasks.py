"""
Task-based synthesis API endpoints - v2 (CosyVoice2)
"""

import asyncio
import hashlib
import os
import time
import uuid
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.models.synthesis import CrossLingualWithCacheRequest
from app.core.synthesis_engine import SynthesisEngine
from app.core.voice_manager import VoiceManager
from app.dependencies import get_synthesis_engine

router = APIRouter()

# Global task storage
tasks_storage: Dict[str, Dict] = {}
tasks_lock = asyncio.Lock()


class TaskRequest(BaseModel):
    """Task-based synthesis request"""
    text: str = Field(..., description="Text to synthesize", max_length=1000)
    voice_id: str = Field(..., description="Cached voice ID")
    format: str = Field("wav", description="Output audio format")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed multiplier")


class TaskResponse(BaseModel):
    """Task registration response"""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status: 'registered', 'processing', 'completed', 'failed'")
    file_path: str = Field(..., description="Pre-allocated file path")
    audio_url: str = Field(..., description="Pre-allocated audio URL")
    estimated_duration: Optional[float] = Field(None, description="Estimated processing time")
    created_at: str = Field(..., description="Task creation timestamp")


class TaskStatusResponse(BaseModel):
    """Task status response"""
    task_id: str = Field(..., description="Task identifier")
    status: str = Field(..., description="Current task status")
    file_path: str = Field(..., description="File path")
    audio_url: str = Field(..., description="Audio URL")
    progress: float = Field(0.0, description="Progress percentage (0.0-1.0)")
    duration: Optional[float] = Field(None, description="Actual audio duration")
    synthesis_time: Optional[float] = Field(None, description="Time taken for synthesis")
    created_at: str = Field(..., description="Task creation timestamp")
    completed_at: Optional[str] = Field(None, description="Task completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")


def generate_file_path(text: str, voice_id: str, format: str) -> tuple[str, str]:
    """Generate pre-allocated file path and URL"""
    content_hash = hashlib.md5(f"{text}_{voice_id}_{format}".encode()).hexdigest()[:8]
    filename = f"v2_task_{content_hash}.{format}"
    file_path = os.path.join("outputs", filename)
    audio_url = f"/api/v2/audio/{filename}"
    return file_path, audio_url


async def process_task_background(task_id: str, request: TaskRequest, synthesis_engine: SynthesisEngine):
    """Background task processing"""
    try:
        async with tasks_lock:
            if task_id not in tasks_storage:
                return
            tasks_storage[task_id]["status"] = "processing"
            tasks_storage[task_id]["progress"] = 0.1

        synthesis_request = CrossLingualWithCacheRequest(
            text=request.text,
            voice_id=request.voice_id,
            format=request.format,
            speed=request.speed,
            stream=False
        )

        async with tasks_lock:
            if task_id in tasks_storage:
                tasks_storage[task_id]["progress"] = 0.3

        start_time = time.time()
        result = await synthesis_engine.synthesize_cross_lingual_with_cache(synthesis_request)
        end_time = time.time()

        if result.file_path and os.path.exists(result.file_path):
            target_path = tasks_storage[task_id]["file_path"]
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(result.file_path, target_path)

        async with tasks_lock:
            if task_id in tasks_storage:
                tasks_storage[task_id].update({
                    "status": "completed",
                    "progress": 1.0,
                    "duration": result.duration,
                    "synthesis_time": end_time - start_time,
                    "completed_at": datetime.now().isoformat()
                })

    except Exception as e:
        async with tasks_lock:
            if task_id in tasks_storage:
                tasks_storage[task_id].update({
                    "status": "failed",
                    "progress": 0.0,
                    "error_message": str(e),
                    "completed_at": datetime.now().isoformat()
                })


@router.post("/cross-lingual/task", response_model=TaskResponse)
async def create_synthesis_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks,
    synthesis_engine: SynthesisEngine = Depends(get_synthesis_engine)
):
    """Create a new synthesis task with pre-allocated file path (CosyVoice2)"""

    task_id = str(uuid.uuid4())
    file_path, audio_url = generate_file_path(request.text, request.voice_id, request.format)
    estimated_duration = len(request.text) * 0.15

    task_data = {
        "task_id": task_id,
        "status": "registered",
        "file_path": file_path,
        "audio_url": audio_url,
        "progress": 0.0,
        "request": request.dict(),
        "created_at": datetime.now().isoformat(),
        "estimated_duration": estimated_duration
    }

    async with tasks_lock:
        tasks_storage[task_id] = task_data

    if synthesis_engine:
        background_tasks.add_task(process_task_background, task_id, request, synthesis_engine)

    return TaskResponse(
        task_id=task_id,
        status="registered",
        file_path=file_path,
        audio_url=audio_url,
        estimated_duration=estimated_duration,
        created_at=task_data["created_at"]
    )


@router.get("/cross-lingual/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get task status and progress"""

    async with tasks_lock:
        if task_id not in tasks_storage:
            raise HTTPException(status_code=404, detail="Task not found")

        task_data = tasks_storage[task_id]

    return TaskStatusResponse(
        task_id=task_id,
        status=task_data["status"],
        file_path=task_data["file_path"],
        audio_url=task_data["audio_url"],
        progress=task_data["progress"],
        duration=task_data.get("duration"),
        synthesis_time=task_data.get("synthesis_time"),
        created_at=task_data["created_at"],
        completed_at=task_data.get("completed_at"),
        error_message=task_data.get("error_message")
    )


@router.get("/cross-lingual/tasks")
async def list_tasks(limit: int = 50, status: Optional[str] = None):
    """List all tasks with optional status filter"""

    async with tasks_lock:
        all_tasks = list(tasks_storage.values())

    if status:
        all_tasks = [task for task in all_tasks if task["status"] == status]

    all_tasks.sort(key=lambda x: x["created_at"], reverse=True)
    all_tasks = all_tasks[:limit]

    return {
        "tasks": all_tasks,
        "total": len(all_tasks),
        "status_filter": status
    }


@router.delete("/cross-lingual/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its associated file"""

    async with tasks_lock:
        if task_id not in tasks_storage:
            raise HTTPException(status_code=404, detail="Task not found")

        task_data = tasks_storage[task_id]

        file_path = task_data["file_path"]
        if os.path.exists(file_path):
            os.remove(file_path)

        del tasks_storage[task_id]

    return {"message": f"Task {task_id} deleted successfully"}
