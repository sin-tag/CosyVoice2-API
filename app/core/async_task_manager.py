"""
Async Task Manager for Chatterbox TTS
Handles background synthesis tasks with sequential processing queue
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional, Any, Callable
from enum import Enum
from pydantic import BaseModel, Field
from collections import deque

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"  # Added: task is in queue waiting
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SynthesisTask(BaseModel):
    """Represents a background synthesis task"""
    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    progress: float = Field(default=0.0, description="Progress 0.0-1.0")
    message: str = Field(default="Task queued")
    queue_position: int = Field(default=0, description="Position in queue (0 = processing)")

    # Input parameters
    text: str = Field(...)
    voice_id: Optional[str] = None
    language: str = "en"
    format: str = "wav"
    exaggeration: float = 0.5

    # Output
    audio_url: Optional[str] = None
    file_path: Optional[str] = None
    duration: Optional[float] = None
    synthesis_time: Optional[float] = None
    error_message: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AsyncTaskManager:
    """
    Manages background synthesis tasks with sequential processing.

    Tasks are queued and processed one at a time because Chatterbox model
    is NOT thread-safe and cannot handle concurrent inference.
    """

    def __init__(self, max_concurrent: int = 1):
        self.tasks: Dict[str, SynthesisTask] = {}
        # Force max_concurrent=1 because model is not thread-safe
        self.max_concurrent = 1
        self._lock = asyncio.Lock()
        self._queue: deque = deque()  # Task queue
        self._processing = False  # Is worker processing?
        self._worker_task: Optional[asyncio.Task] = None
        logger.info(f"AsyncTaskManager initialized (sequential processing, queue-based)")

    async def create_task(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "en",
        format: str = "wav",
        exaggeration: float = 0.5
    ) -> SynthesisTask:
        """Create a new synthesis task"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        # Calculate queue position
        queue_position = len(self._queue) + (1 if self._processing else 0)

        task = SynthesisTask(
            task_id=task_id,
            text=text,
            voice_id=voice_id,
            language=language,
            format=format,
            exaggeration=exaggeration,
            status=TaskStatus.QUEUED,
            queue_position=queue_position,
            message=f"Queued (position {queue_position})" if queue_position > 0 else "Ready to process"
        )

        async with self._lock:
            self.tasks[task_id] = task

        logger.info(f"Created task {task_id} (queue position: {queue_position})")
        return task

    async def get_task(self, task_id: str) -> Optional[SynthesisTask]:
        """Get task by ID"""
        return self.tasks.get(task_id)

    async def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        audio_url: Optional[str] = None,
        file_path: Optional[str] = None,
        duration: Optional[float] = None,
        synthesis_time: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> Optional[SynthesisTask]:
        """Update task status"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        async with self._lock:
            if status:
                task.status = status
                if status == TaskStatus.PROCESSING and not task.started_at:
                    task.started_at = datetime.utcnow()
                elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    task.completed_at = datetime.utcnow()

            if progress is not None:
                task.progress = progress
            if message:
                task.message = message
            if audio_url:
                task.audio_url = audio_url
            if file_path:
                task.file_path = file_path
            if duration is not None:
                task.duration = duration
            if synthesis_time is not None:
                task.synthesis_time = synthesis_time
            if error_message:
                task.error_message = error_message

        return task

    async def enqueue_task(self, task_id: str, synthesis_func: Callable, *args, **kwargs):
        """
        Add task to queue and start worker if not running.
        Returns immediately - task will be processed in order.
        """
        # Add to queue
        self._queue.append({
            "task_id": task_id,
            "func": synthesis_func,
            "args": args,
            "kwargs": kwargs
        })

        logger.info(f"Task {task_id} enqueued (queue size: {len(self._queue)})")

        # Update queue positions for all queued tasks
        await self._update_queue_positions()

        # Start worker if not running
        if not self._processing:
            asyncio.create_task(self._process_queue())

    async def _update_queue_positions(self):
        """Update queue position for all queued tasks"""
        position = 1 if self._processing else 0
        for item in self._queue:
            task = self.tasks.get(item["task_id"])
            if task and task.status == TaskStatus.QUEUED:
                task.queue_position = position
                task.message = f"Queued (position {position})"
                position += 1

    async def _process_queue(self):
        """Process tasks from queue sequentially"""
        if self._processing:
            return  # Already processing

        self._processing = True
        logger.info("Queue worker started")

        try:
            while self._queue:
                # Get next task from queue
                item = self._queue.popleft()
                task_id = item["task_id"]
                synthesis_func = item["func"]
                args = item["args"]
                kwargs = item["kwargs"]

                task = await self.get_task(task_id)
                if not task:
                    logger.error(f"Task {task_id} not found, skipping")
                    continue

                logger.info(f"Processing task {task_id} (remaining in queue: {len(self._queue)})")

                # Update queue positions for remaining tasks
                await self._update_queue_positions()

                try:
                    await self.update_task(
                        task_id,
                        status=TaskStatus.PROCESSING,
                        progress=0.1,
                        message="Starting synthesis..."
                    )
                    task.queue_position = 0

                    # Run the synthesis function
                    result = await synthesis_func(*args, **kwargs)

                    await self.update_task(
                        task_id,
                        status=TaskStatus.COMPLETED,
                        progress=1.0,
                        message="Synthesis completed",
                        audio_url=result.get("audio_url"),
                        file_path=result.get("file_path"),
                        duration=result.get("duration"),
                        synthesis_time=result.get("synthesis_time")
                    )

                    logger.info(f"Task {task_id} completed successfully")

                except Exception as e:
                    logger.error(f"Task {task_id} failed: {e}")
                    await self.update_task(
                        task_id,
                        status=TaskStatus.FAILED,
                        progress=0.0,
                        message="Synthesis failed",
                        error_message=str(e)
                    )

        finally:
            self._processing = False
            logger.info("Queue worker stopped")

    # Keep old method for backward compatibility but redirect to enqueue
    async def run_task(self, task_id: str, synthesis_func: Callable, *args, **kwargs):
        """Run synthesis task - adds to queue for sequential processing"""
        await self.enqueue_task(task_id, synthesis_func, *args, **kwargs)

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50
    ) -> list[SynthesisTask]:
        """List tasks, optionally filtered by status"""
        tasks = list(self.tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        # Sort by created_at descending
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        return tasks[:limit]

    async def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove tasks older than max_age_hours"""
        now = datetime.utcnow()
        to_remove = []

        for task_id, task in self.tasks.items():
            age = (now - task.created_at).total_seconds() / 3600
            if age > max_age_hours and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                to_remove.append(task_id)

        async with self._lock:
            for task_id in to_remove:
                del self.tasks[task_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")


# Global instance
_task_manager: Optional[AsyncTaskManager] = None


def get_task_manager() -> AsyncTaskManager:
    """Get global task manager instance"""
    global _task_manager
    if _task_manager is None:
        _task_manager = AsyncTaskManager()
    return _task_manager


async def initialize_task_manager(max_concurrent: int = 4) -> AsyncTaskManager:
    """Initialize global task manager"""
    global _task_manager
    _task_manager = AsyncTaskManager(max_concurrent=max_concurrent)
    return _task_manager
