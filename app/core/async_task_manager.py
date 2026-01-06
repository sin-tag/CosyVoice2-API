"""
Async Task Manager for Chatterbox TTS
Handles background synthesis tasks
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SynthesisTask(BaseModel):
    """Represents a background synthesis task"""
    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    progress: float = Field(default=0.0, description="Progress 0.0-1.0")
    message: str = Field(default="Task queued")

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
    """Manages background synthesis tasks"""

    def __init__(self, max_concurrent: int = 4):
        self.tasks: Dict[str, SynthesisTask] = {}
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = asyncio.Lock()
        logger.info(f"AsyncTaskManager initialized (max_concurrent={max_concurrent})")

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

        task = SynthesisTask(
            task_id=task_id,
            text=text,
            voice_id=voice_id,
            language=language,
            format=format,
            exaggeration=exaggeration
        )

        async with self._lock:
            self.tasks[task_id] = task

        logger.info(f"Created task {task_id}")
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

    async def run_task(self, task_id: str, synthesis_func, *args, **kwargs):
        """Run synthesis task in background"""
        async with self._semaphore:
            task = await self.get_task(task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            try:
                await self.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0.1,
                    message="Starting synthesis..."
                )

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
