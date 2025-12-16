"""
Task-based synthesis API endpoints - v3 (CosyVoice3)
Includes scheduled background rendering support
"""

import asyncio
import hashlib
import os
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from app.models.synthesis import CrossLingualWithCacheRequest
from app.core.synthesis_engine_v3 import SynthesisEngineV3
from app.core.voice_manager_v3 import VoiceManagerV3

logger = logging.getLogger(__name__)

router = APIRouter()

# Global task storage for v3
tasks_storage_v3: Dict[str, Dict] = {}
tasks_lock_v3 = asyncio.Lock()

# Schedule queue for background rendering
schedule_queue_v3: Dict[str, Dict] = {}
schedule_lock_v3 = asyncio.Lock()

# Background worker status
background_worker_running = False
background_worker_task: Optional[asyncio.Task] = None


class TaskStatus(str, Enum):
    """Task status enum"""
    PENDING = "pending"          # Task registered, waiting to be scheduled
    SCHEDULED = "scheduled"      # Task added to render queue
    PROCESSING = "processing"    # Currently rendering
    COMPLETED = "completed"      # Render completed, file ready
    FAILED = "failed"           # Render failed
    CANCELLED = "cancelled"     # Task cancelled


class TaskPriority(str, Enum):
    """Task priority for scheduling"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskRequest(BaseModel):
    """Task-based synthesis request"""
    text: str = Field(..., description="Text to synthesize", max_length=2000)
    voice_id: str = Field(..., description="Cached voice ID")
    format: str = Field("wav", description="Output audio format")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    instruct_text: Optional[str] = Field(None, description="Instruction for voice control")


class ScheduleTaskRequest(BaseModel):
    """Schedule task request - register task without immediate processing"""
    text: str = Field(..., description="Text to synthesize", max_length=2000)
    voice_id: str = Field(..., description="Cached voice ID")
    format: str = Field("wav", description="Output audio format: wav, mp3, flac")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed multiplier")
    instruct_text: Optional[str] = Field(None, description="Instruction for voice control (CosyVoice3)")
    priority: TaskPriority = Field(TaskPriority.NORMAL, description="Task priority")
    callback_url: Optional[str] = Field(None, description="Webhook URL to call when task completes")
    metadata: Optional[Dict] = Field(None, description="Custom metadata to store with task")


class TaskResponse(BaseModel):
    """Task registration response"""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Task status: 'pending', 'scheduled', 'processing', 'completed', 'failed'")
    file_path: str = Field(..., description="Pre-allocated file path")
    audio_url: str = Field(..., description="Pre-allocated audio URL")
    estimated_duration: Optional[float] = Field(None, description="Estimated processing time")
    created_at: str = Field(..., description="Task creation timestamp")


class ScheduleTaskResponse(BaseModel):
    """Schedule task response - returned when task is registered for background processing"""
    task_id: str = Field(..., description="Unique task identifier for tracking")
    status: TaskStatus = Field(..., description="Current task status")
    message: str = Field(..., description="Status message")
    file_path: Optional[str] = Field(None, description="Pre-allocated file path (available after completion)")
    audio_url: Optional[str] = Field(None, description="Audio URL (available after completion)")
    queue_position: Optional[int] = Field(None, description="Position in render queue")
    estimated_wait_time: Optional[float] = Field(None, description="Estimated wait time in seconds")
    created_at: str = Field(..., description="Task creation timestamp")
    priority: TaskPriority = Field(..., description="Task priority")
    metadata: Optional[Dict] = Field(None, description="Custom metadata")


class TaskStatusResponse(BaseModel):
    """Task status response"""
    task_id: str = Field(..., description="Task identifier")
    status: str = Field(..., description="Current task status")
    file_path: Optional[str] = Field(None, description="File path")
    audio_url: Optional[str] = Field(None, description="Audio URL")
    progress: float = Field(0.0, description="Progress percentage (0.0-1.0)")
    duration: Optional[float] = Field(None, description="Actual audio duration in seconds")
    synthesis_time: Optional[float] = Field(None, description="Time taken for synthesis in seconds")
    created_at: str = Field(..., description="Task creation timestamp")
    started_at: Optional[str] = Field(None, description="Processing start timestamp")
    completed_at: Optional[str] = Field(None, description="Task completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    queue_position: Optional[int] = Field(None, description="Current position in queue (if pending/scheduled)")
    priority: Optional[str] = Field(None, description="Task priority")
    metadata: Optional[Dict] = Field(None, description="Custom metadata")


def get_voice_manager_v3(request: Request) -> VoiceManagerV3:
    """Dependency to get voice manager v3 from app state"""
    voice_manager = getattr(request.app.state, 'voice_manager_v3', None)
    if not voice_manager:
        raise HTTPException(status_code=503, detail="CosyVoice3 voice manager not available")
    if not voice_manager.is_ready():
        raise HTTPException(status_code=503, detail="CosyVoice3 voice manager is not ready")
    return voice_manager


def get_synthesis_engine_v3(voice_manager: VoiceManagerV3 = Depends(get_voice_manager_v3)) -> SynthesisEngineV3:
    """Dependency to get synthesis engine v3"""
    return SynthesisEngineV3(voice_manager)


def generate_file_path_v3(text: str, voice_id: str, format: str) -> tuple[str, str]:
    """Generate pre-allocated file path and URL for v3"""
    content_hash = hashlib.md5(f"{text}_{voice_id}_{format}_v3".encode()).hexdigest()[:8]
    filename = f"v3_task_{content_hash}.{format}"
    file_path = os.path.join("outputs", filename)
    audio_url = f"/api/v3/audio/{filename}"
    return file_path, audio_url


async def process_task_background_v3(task_id: str, request: TaskRequest, synthesis_engine: SynthesisEngineV3):
    """Background task processing for v3"""
    try:
        async with tasks_lock_v3:
            if task_id not in tasks_storage_v3:
                return
            tasks_storage_v3[task_id]["status"] = "processing"
            tasks_storage_v3[task_id]["progress"] = 0.1

        synthesis_request = CrossLingualWithCacheRequest(
            text=request.text,
            voice_id=request.voice_id,
            format=request.format,
            speed=request.speed,
            stream=False
        )

        async with tasks_lock_v3:
            if task_id in tasks_storage_v3:
                tasks_storage_v3[task_id]["progress"] = 0.3

        start_time = time.time()
        result = await synthesis_engine.synthesize_cross_lingual_with_cache(synthesis_request)
        end_time = time.time()

        if result.file_path and os.path.exists(result.file_path):
            target_path = tasks_storage_v3[task_id]["file_path"]
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            if os.path.exists(target_path):
                os.remove(target_path)
            os.rename(result.file_path, target_path)

        async with tasks_lock_v3:
            if task_id in tasks_storage_v3:
                tasks_storage_v3[task_id].update({
                    "status": "completed",
                    "progress": 1.0,
                    "duration": result.duration,
                    "synthesis_time": end_time - start_time,
                    "completed_at": datetime.now().isoformat()
                })

    except Exception as e:
        async with tasks_lock_v3:
            if task_id in tasks_storage_v3:
                tasks_storage_v3[task_id].update({
                    "status": "failed",
                    "progress": 0.0,
                    "error_message": str(e),
                    "completed_at": datetime.now().isoformat()
                })


@router.post("/cross-lingual/task", response_model=TaskResponse)
async def create_synthesis_task(
    request: TaskRequest,
    background_tasks: BackgroundTasks,
    synthesis_engine: SynthesisEngineV3 = Depends(get_synthesis_engine_v3)
):
    """Create a new synthesis task with pre-allocated file path (CosyVoice3)"""

    task_id = str(uuid.uuid4())
    file_path, audio_url = generate_file_path_v3(request.text, request.voice_id, request.format)
    estimated_duration = len(request.text) * 0.12  # CosyVoice3 is slightly faster

    task_data = {
        "task_id": task_id,
        "status": "registered",
        "file_path": file_path,
        "audio_url": audio_url,
        "progress": 0.0,
        "request": request.dict(),
        "created_at": datetime.now().isoformat(),
        "estimated_duration": estimated_duration,
        "version": "v3"
    }

    async with tasks_lock_v3:
        tasks_storage_v3[task_id] = task_data

    if synthesis_engine:
        background_tasks.add_task(process_task_background_v3, task_id, request, synthesis_engine)

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
    """Get task status and progress (v3)"""

    async with tasks_lock_v3:
        if task_id not in tasks_storage_v3:
            raise HTTPException(status_code=404, detail="Task not found")

        task_data = tasks_storage_v3[task_id]

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
    """List all tasks with optional status filter (v3)"""

    async with tasks_lock_v3:
        all_tasks = list(tasks_storage_v3.values())

    if status:
        all_tasks = [task for task in all_tasks if task["status"] == status]

    all_tasks.sort(key=lambda x: x["created_at"], reverse=True)
    all_tasks = all_tasks[:limit]

    return {
        "tasks": all_tasks,
        "total": len(all_tasks),
        "status_filter": status,
        "version": "v3"
    }


@router.delete("/cross-lingual/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its associated file (v3)"""

    async with tasks_lock_v3:
        if task_id not in tasks_storage_v3:
            raise HTTPException(status_code=404, detail="Task not found")

        task_data = tasks_storage_v3[task_id]

        file_path = task_data.get("file_path")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        del tasks_storage_v3[task_id]

    return {"message": f"Task {task_id} deleted successfully", "version": "v3"}


# ============================================
# SCHEDULE-BASED BACKGROUND RENDERING API
# ============================================
# Workflow:
# 1. POST /schedule/register - Register task, get task_id (status: pending)
# 2. POST /schedule/render/{task_id} - Start background rendering (status: processing)
# 3. GET /schedule/status/{task_id} - Check status, get audio_url when completed
# ============================================


def get_priority_weight(priority: TaskPriority) -> int:
    """Get priority weight for sorting (higher = more priority)"""
    weights = {
        TaskPriority.LOW: 1,
        TaskPriority.NORMAL: 2,
        TaskPriority.HIGH: 3,
        TaskPriority.URGENT: 4
    }
    return weights.get(priority, 2)


def calculate_queue_position(task_id: str) -> int:
    """Calculate current position in queue"""
    pending_tasks = [
        (tid, data) for tid, data in schedule_queue_v3.items()
        if data["status"] in [TaskStatus.PENDING.value, TaskStatus.SCHEDULED.value]
    ]
    # Sort by priority (desc) and created_at (asc)
    pending_tasks.sort(
        key=lambda x: (-get_priority_weight(TaskPriority(x[1].get("priority", "normal"))), x[1]["created_at"])
    )
    for i, (tid, _) in enumerate(pending_tasks):
        if tid == task_id:
            return i + 1
    return 0


async def process_scheduled_task(task_id: str, voice_manager: VoiceManagerV3):
    """Process a single scheduled task"""
    global schedule_queue_v3

    try:
        async with schedule_lock_v3:
            if task_id not in schedule_queue_v3:
                return
            task_data = schedule_queue_v3[task_id]
            task_data["status"] = TaskStatus.PROCESSING.value
            task_data["started_at"] = datetime.now().isoformat()
            task_data["progress"] = 0.1

        # Get request data
        request_data = task_data["request"]

        # Create synthesis engine
        synthesis_engine = SynthesisEngineV3(voice_manager)

        # Generate file path
        file_path, audio_url = generate_file_path_v3(
            request_data["text"],
            request_data["voice_id"],
            request_data["format"]
        )

        async with schedule_lock_v3:
            if task_id in schedule_queue_v3:
                schedule_queue_v3[task_id]["file_path"] = file_path
                schedule_queue_v3[task_id]["audio_url"] = audio_url
                schedule_queue_v3[task_id]["progress"] = 0.3

        # Perform synthesis
        synthesis_request = CrossLingualWithCacheRequest(
            text=request_data["text"],
            voice_id=request_data["voice_id"],
            format=request_data["format"],
            speed=request_data.get("speed", 1.0),
            stream=False
        )

        start_time = time.time()
        result = await synthesis_engine.synthesize_cross_lingual_with_cache(synthesis_request)
        end_time = time.time()

        # Move result file to target path
        if result.file_path and os.path.exists(result.file_path):
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(result.file_path, file_path)

        # Update task status
        async with schedule_lock_v3:
            if task_id in schedule_queue_v3:
                schedule_queue_v3[task_id].update({
                    "status": TaskStatus.COMPLETED.value,
                    "progress": 1.0,
                    "duration": result.duration,
                    "synthesis_time": end_time - start_time,
                    "completed_at": datetime.now().isoformat()
                })

        logger.info(f"Scheduled task {task_id} completed successfully")

        # TODO: Call webhook if callback_url is provided
        callback_url = task_data.get("callback_url")
        if callback_url:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    await session.post(callback_url, json={
                        "task_id": task_id,
                        "status": "completed",
                        "audio_url": audio_url,
                        "duration": result.duration
                    })
            except Exception as e:
                logger.warning(f"Failed to call webhook for task {task_id}: {e}")

    except Exception as e:
        logger.error(f"Scheduled task {task_id} failed: {e}")
        async with schedule_lock_v3:
            if task_id in schedule_queue_v3:
                schedule_queue_v3[task_id].update({
                    "status": TaskStatus.FAILED.value,
                    "progress": 0.0,
                    "error_message": str(e),
                    "completed_at": datetime.now().isoformat()
                })


@router.post("/schedule/register", response_model=ScheduleTaskResponse)
async def register_scheduled_task(request: ScheduleTaskRequest):
    """
    Register a new task for background rendering (Step 1)

    This endpoint registers the task but does NOT start rendering.
    Use POST /schedule/render/{task_id} to start the rendering process.

    Workflow:
    1. POST /schedule/register -> Returns task_id (status: pending)
    2. POST /schedule/render/{task_id} -> Starts background rendering (status: processing)
    3. GET /schedule/status/{task_id} -> Check status, get audio_url when completed
    """
    task_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()

    task_data = {
        "task_id": task_id,
        "status": TaskStatus.PENDING.value,
        "request": {
            "text": request.text,
            "voice_id": request.voice_id,
            "format": request.format,
            "speed": request.speed,
            "instruct_text": request.instruct_text
        },
        "priority": request.priority.value,
        "callback_url": request.callback_url,
        "metadata": request.metadata,
        "created_at": created_at,
        "progress": 0.0,
        "file_path": None,
        "audio_url": None,
        "version": "v3"
    }

    async with schedule_lock_v3:
        schedule_queue_v3[task_id] = task_data

    # Calculate estimated wait time based on queue
    queue_position = calculate_queue_position(task_id)
    estimated_wait_time = queue_position * len(request.text) * 0.12  # ~0.12s per character

    logger.info(f"Registered scheduled task {task_id} with priority {request.priority.value}")

    return ScheduleTaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Task registered successfully. Call POST /schedule/render/{task_id} to start rendering.",
        file_path=None,
        audio_url=None,
        queue_position=queue_position,
        estimated_wait_time=estimated_wait_time,
        created_at=created_at,
        priority=request.priority,
        metadata=request.metadata
    )


@router.post("/schedule/render/{task_id}")
async def start_scheduled_render(
    task_id: str,
    background_tasks: BackgroundTasks,
    voice_manager: VoiceManagerV3 = Depends(get_voice_manager_v3)
):
    """
    Start background rendering for a registered task (Step 2)

    This endpoint triggers the actual voice synthesis in the background.
    The task must have been registered first using POST /schedule/register.

    After calling this endpoint, use GET /schedule/status/{task_id} to monitor progress.
    """
    async with schedule_lock_v3:
        if task_id not in schedule_queue_v3:
            raise HTTPException(status_code=404, detail="Task not found. Register task first using POST /schedule/register")

        task_data = schedule_queue_v3[task_id]

        if task_data["status"] == TaskStatus.PROCESSING.value:
            raise HTTPException(status_code=400, detail="Task is already being processed")

        if task_data["status"] == TaskStatus.COMPLETED.value:
            return {
                "task_id": task_id,
                "status": "completed",
                "message": "Task already completed",
                "audio_url": task_data.get("audio_url"),
                "file_path": task_data.get("file_path")
            }

        if task_data["status"] == TaskStatus.FAILED.value:
            # Allow retry
            task_data["status"] = TaskStatus.SCHEDULED.value
            task_data["error_message"] = None
        else:
            task_data["status"] = TaskStatus.SCHEDULED.value

    # Add to background tasks
    background_tasks.add_task(process_scheduled_task, task_id, voice_manager)

    logger.info(f"Started background rendering for task {task_id}")

    return {
        "task_id": task_id,
        "status": "scheduled",
        "message": "Background rendering started. Use GET /schedule/status/{task_id} to check progress.",
        "version": "v3"
    }


@router.get("/schedule/status/{task_id}", response_model=TaskStatusResponse)
async def get_scheduled_task_status(task_id: str):
    """
    Get status of a scheduled task (Step 3)

    Check the status and progress of a task. When status is 'completed',
    the audio_url field will contain the URL to download the generated audio.

    Status values:
    - pending: Task registered, waiting for render to start
    - scheduled: Task added to render queue
    - processing: Currently rendering
    - completed: Rendering done, audio ready for download
    - failed: Rendering failed (check error_message)
    - cancelled: Task was cancelled
    """
    async with schedule_lock_v3:
        if task_id not in schedule_queue_v3:
            raise HTTPException(status_code=404, detail="Task not found")

        task_data = schedule_queue_v3[task_id]

    # Calculate queue position for pending/scheduled tasks
    queue_position = None
    if task_data["status"] in [TaskStatus.PENDING.value, TaskStatus.SCHEDULED.value]:
        queue_position = calculate_queue_position(task_id)

    return TaskStatusResponse(
        task_id=task_id,
        status=task_data["status"],
        file_path=task_data.get("file_path"),
        audio_url=task_data.get("audio_url"),
        progress=task_data.get("progress", 0.0),
        duration=task_data.get("duration"),
        synthesis_time=task_data.get("synthesis_time"),
        created_at=task_data["created_at"],
        started_at=task_data.get("started_at"),
        completed_at=task_data.get("completed_at"),
        error_message=task_data.get("error_message"),
        queue_position=queue_position,
        priority=task_data.get("priority"),
        metadata=task_data.get("metadata")
    )


@router.get("/schedule/tasks")
async def list_scheduled_tasks(
    limit: int = 50,
    status: Optional[str] = None,
    priority: Optional[str] = None
):
    """
    List all scheduled tasks with optional filters

    Query parameters:
    - limit: Maximum number of tasks to return (default: 50)
    - status: Filter by status (pending, scheduled, processing, completed, failed)
    - priority: Filter by priority (low, normal, high, urgent)
    """
    async with schedule_lock_v3:
        all_tasks = list(schedule_queue_v3.values())

    # Apply filters
    if status:
        all_tasks = [task for task in all_tasks if task["status"] == status]
    if priority:
        all_tasks = [task for task in all_tasks if task.get("priority") == priority]

    # Sort by priority (desc) and created_at (desc)
    all_tasks.sort(
        key=lambda x: (-get_priority_weight(TaskPriority(x.get("priority", "normal"))), x["created_at"]),
        reverse=True
    )
    all_tasks = all_tasks[:limit]

    # Count by status
    status_counts = {}
    async with schedule_lock_v3:
        for task in schedule_queue_v3.values():
            s = task["status"]
            status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "tasks": all_tasks,
        "total": len(all_tasks),
        "status_filter": status,
        "priority_filter": priority,
        "status_counts": status_counts,
        "version": "v3"
    }


@router.delete("/schedule/task/{task_id}")
async def cancel_scheduled_task(task_id: str):
    """
    Cancel or delete a scheduled task

    - If task is pending/scheduled: Cancels the task
    - If task is completed: Deletes the task and audio file
    - If task is processing: Cannot cancel (must wait for completion)
    """
    async with schedule_lock_v3:
        if task_id not in schedule_queue_v3:
            raise HTTPException(status_code=404, detail="Task not found")

        task_data = schedule_queue_v3[task_id]

        if task_data["status"] == TaskStatus.PROCESSING.value:
            raise HTTPException(status_code=400, detail="Cannot cancel task while processing. Please wait for completion.")

        # Delete audio file if exists
        file_path = task_data.get("file_path")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        del schedule_queue_v3[task_id]

    logger.info(f"Cancelled/deleted scheduled task {task_id}")

    return {
        "task_id": task_id,
        "message": "Task cancelled/deleted successfully",
        "version": "v3"
    }


@router.post("/schedule/render-all")
async def render_all_pending_tasks(
    background_tasks: BackgroundTasks,
    voice_manager: VoiceManagerV3 = Depends(get_voice_manager_v3),
    max_tasks: int = 10
):
    """
    Start rendering for all pending tasks (batch processing)

    This endpoint triggers background rendering for up to max_tasks pending tasks,
    sorted by priority (urgent first) and creation time.
    """
    async with schedule_lock_v3:
        pending_tasks = [
            (tid, data) for tid, data in schedule_queue_v3.items()
            if data["status"] == TaskStatus.PENDING.value
        ]

    # Sort by priority (desc) and created_at (asc)
    pending_tasks.sort(
        key=lambda x: (-get_priority_weight(TaskPriority(x[1].get("priority", "normal"))), x[1]["created_at"])
    )

    # Limit number of tasks
    tasks_to_render = pending_tasks[:max_tasks]

    rendered_count = 0
    for task_id, task_data in tasks_to_render:
        async with schedule_lock_v3:
            schedule_queue_v3[task_id]["status"] = TaskStatus.SCHEDULED.value
        background_tasks.add_task(process_scheduled_task, task_id, voice_manager)
        rendered_count += 1

    logger.info(f"Started rendering {rendered_count} pending tasks")

    return {
        "message": f"Started rendering {rendered_count} tasks",
        "tasks_started": rendered_count,
        "tasks_remaining": len(pending_tasks) - rendered_count,
        "version": "v3"
    }


@router.get("/schedule/queue-stats")
async def get_queue_statistics():
    """
    Get statistics about the scheduled task queue

    Returns counts by status and priority, plus average processing times.
    """
    async with schedule_lock_v3:
        all_tasks = list(schedule_queue_v3.values())

    # Count by status
    status_counts = {}
    priority_counts = {}
    total_synthesis_time = 0.0
    completed_count = 0

    for task in all_tasks:
        # Status counts
        status = task["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

        # Priority counts
        priority = task.get("priority", "normal")
        priority_counts[priority] = priority_counts.get(priority, 0) + 1

        # Average synthesis time
        if task["status"] == TaskStatus.COMPLETED.value and task.get("synthesis_time"):
            total_synthesis_time += task["synthesis_time"]
            completed_count += 1

    avg_synthesis_time = total_synthesis_time / completed_count if completed_count > 0 else 0

    return {
        "total_tasks": len(all_tasks),
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "average_synthesis_time": round(avg_synthesis_time, 3),
        "completed_tasks": completed_count,
        "version": "v3"
    }
