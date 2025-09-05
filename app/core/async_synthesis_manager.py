"""
Async Synthesis Manager for handling concurrent synthesis tasks
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Set
from enum import Enum

from app.core.synthesis_engine import SynthesisEngine
from app.models.synthesis import CrossLingualAsyncRequest, AsyncTaskResponse, AsyncTaskStatusResponse

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AsyncTask:
    """Async synthesis task"""
    
    def __init__(self, task_id: str, request: CrossLingualAsyncRequest):
        self.task_id = task_id
        self.request = request
        self.status = TaskStatus.PENDING
        self.progress = 0.0
        self.message = "Task created"
        self.audio_url: Optional[str] = None
        self.file_path: Optional[str] = None
        self.duration: Optional[float] = None
        self.synthesis_time: Optional[float] = None
        self.error_message: Optional[str] = None
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None


class AsyncSynthesisManager:
    """Manager for handling async synthesis tasks"""

    def __init__(self, synthesis_engine: SynthesisEngine, max_concurrent: int = 4):
        self.synthesis_engine = synthesis_engine
        self.max_concurrent = max_concurrent  # Keep for reference but don't enforce
        self.tasks: Dict[str, AsyncTask] = {}
        # NO LIMITS - Full parallel processing!
        self._task_lock = asyncio.Lock()  # Keep for task dict protection only
        self.running_tasks: Set[str] = set()
        self.running = False
        self._lock = asyncio.Lock()
        # REMOVED: self._semaphore - No concurrent limits!
        
    async def start(self):
        """Start the async synthesis manager"""
        self.running = True
        logger.info(f"Async synthesis manager started with {self.max_concurrent} concurrent tasks")

    async def stop(self):
        """Stop the async synthesis manager"""
        self.running = False
        # Cancel all running tasks
        for task_id in list(self.running_tasks):
            async with self._lock:
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    if task.status == TaskStatus.PROCESSING:
                        task.status = TaskStatus.FAILED
                        task.error_message = "Server shutdown"
        logger.info("Async synthesis manager stopped")
        
    async def create_task(self, request: CrossLingualAsyncRequest) -> AsyncTaskResponse:
        """Create a new async synthesis task"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        async with self._lock:
            task = AsyncTask(task_id, request)
            self.tasks[task_id] = task

        # Create async task (non-blocking)
        asyncio.create_task(self._process_task_async(task_id))

        # Estimate completion time based on text length
        estimated_time = max(5.0, len(request.text) * 0.1)  # Rough estimate

        logger.info(f"Created async task {task_id} for text: {request.text[:50]}...")

        return AsyncTaskResponse(
            success=True,
            task_id=task_id,
            message="Task created successfully",
            status=TaskStatus.PENDING,
            estimated_time=estimated_time
        )
        
    async def get_task_status(self, task_id: str) -> AsyncTaskStatusResponse:
        """Get status of an async task"""
        async with self._lock:
            task = self.tasks.get(task_id)

        if not task:
            return AsyncTaskStatusResponse(
                success=False,
                task_id=task_id,
                status="not_found",
                progress=0.0,
                message="Task not found"
            )

        return AsyncTaskStatusResponse(
            success=True,
            task_id=task_id,
            status=task.status,
            progress=task.progress,
            message=task.message,
            audio_url=task.audio_url,
            file_path=task.file_path,
            duration=task.duration,
            synthesis_time=task.synthesis_time,
            error_message=task.error_message,
            created_at=task.created_at,
            completed_at=task.completed_at
        )
        
    async def list_tasks(self) -> Dict[str, AsyncTaskStatusResponse]:
        """List all tasks"""
        async with self._lock:
            result = {}
            for task_id, task in self.tasks.items():
                result[task_id] = AsyncTaskStatusResponse(
                    success=True,
                    task_id=task_id,
                    status=task.status,
                    progress=task.progress,
                    message=task.message,
                    audio_url=task.audio_url,
                    file_path=task.file_path,
                    duration=task.duration,
                    synthesis_time=task.synthesis_time,
                    error_message=task.error_message,
                    created_at=task.created_at,
                    completed_at=task.completed_at
                )
            return result
            
    async def cleanup_completed_tasks(self, max_age_hours: int = 24):
        """Clean up completed tasks older than max_age_hours"""
        current_time = datetime.now()
        to_remove = []

        async with self._lock:
            for task_id, task in self.tasks.items():
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    task_time = datetime.fromisoformat(task.created_at)
                    age_hours = (current_time - task_time).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self.tasks[task_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")
            
    async def _process_task_async(self, task_id: str):
        """Process a synthesis task asynchronously - NO LIMITS, full parallel!"""
        # REMOVED: semaphore - No concurrent limits!
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return

            # Add to running tasks
            self.running_tasks.add(task_id)
            task.status = TaskStatus.PROCESSING
            task.progress = 0.1
            task.message = "Starting synthesis..."

        try:
            logger.info(f"Processing task {task_id}")

            # Create synthesis request
            from app.models.synthesis import CrossLingualWithCacheRequest
            synthesis_request = CrossLingualWithCacheRequest(
                text=task.request.text,
                voice_id=task.request.voice_id,
                prompt_text=task.request.prompt_text,
                instruct_text=task.request.instruct_text,
                format=task.request.format,
                speed=task.request.speed,
                stream=False  # Always non-streaming for async
            )

            # Update progress
            async with self._lock:
                task.progress = 0.3
                task.message = "Synthesizing audio..."

            # Run synthesis (this is the main work)
            result = await self.synthesis_engine.synthesize_cross_lingual_with_cache(synthesis_request)

            # Update task with results
            async with self._lock:
                task.status = TaskStatus.COMPLETED
                task.progress = 1.0
                task.message = "Synthesis completed successfully"
                task.audio_url = result.audio_url
                task.file_path = result.file_path
                task.duration = result.duration
                task.synthesis_time = result.synthesis_time
                task.completed_at = datetime.now().isoformat()

            logger.info(f"Task {task_id} completed successfully")

            # Call callback URL if provided
            if task.request.callback_url:
                await self._call_callback_async(task.request.callback_url, task)

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")

            async with self._lock:
                task.status = TaskStatus.FAILED
                task.progress = 0.0
                task.message = "Synthesis failed"
                task.error_message = str(e)
                task.completed_at = datetime.now().isoformat()

        finally:
            # Remove from running tasks
            async with self._lock:
                self.running_tasks.discard(task_id)
                
    async def _call_callback_async(self, callback_url: str, task: AsyncTask):
        """Call callback URL when task is completed"""
        try:
            import aiohttp

            callback_data = {
                "task_id": task.task_id,
                "status": task.status,
                "audio_url": task.audio_url,
                "duration": task.duration,
                "synthesis_time": task.synthesis_time,
                "completed_at": task.completed_at
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(callback_url, json=callback_data, timeout=10) as response:
                    logger.info(f"Callback sent to {callback_url} for task {task.task_id}: {response.status}")

        except Exception as e:
            logger.error(f"Failed to call callback {callback_url} for task {task.task_id}: {e}")
