"""Enhanced Async Task Manager for Streaming Synthesis - Improved resource management and monitoring"""
import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, Optional, Set, List, Any
from enum import Enum
from dataclasses import dataclass, field

from app.core.streaming_synthesis_engine import StreamingSynthesisEngine
from app.models.streaming import (
    StreamingSynthesisRequest, StreamingSession, StreamingStats,
    StreamingError, StreamingConfig
)

logger = logging.getLogger(__name__)

class StreamingTaskStatus(str, Enum):
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class StreamingTask:
    """Enhanced streaming synthesis task with resource tracking"""
    task_id: str
    request: StreamingSynthesisRequest
    session_id: Optional[str] = None
    status: StreamingTaskStatus = StreamingTaskStatus.PENDING
    progress: float = 0.0
    message: str = "Task created"
    chunks_sent: int = 0
    total_bytes: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_activity: float = field(default_factory=time.time)
    
    # Resource tracking
    memory_usage: int = 0  # Estimated memory usage in bytes
    cpu_time: float = 0.0  # CPU time used
    
    # Cancellation support
    cancelled: bool = False
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

class StreamingTaskManager:
    """Enhanced task manager for streaming synthesis with improved resource management"""
    
    def __init__(self, streaming_engine: StreamingSynthesisEngine, config: StreamingConfig = None):
        self.streaming_engine = streaming_engine
        self.config = config or StreamingConfig()
        
        # Task storage
        self.tasks: Dict[str, StreamingTask] = {}
        self.active_tasks: Set[str] = set()
        self.completed_tasks: List[str] = []
        
        # Resource management
        self._task_lock = asyncio.Lock()
        self._resource_lock = asyncio.Lock()
        self.running = False
        
        # Statistics
        self.stats = StreamingStats()
        self._stats_lock = asyncio.Lock()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the streaming task manager"""
        self.running = True
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"Streaming task manager started with config: max_streams={self.config.max_concurrent_streams}")
    
    async def stop(self):
        """Stop the streaming task manager and cleanup resources"""
        self.running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all active tasks
        async with self._task_lock:
            for task_id in list(self.active_tasks):
                await self._cancel_task_internal(task_id, "Manager shutdown")
        
        logger.info("Streaming task manager stopped")
    
    async def create_streaming_task(
        self, 
        request: StreamingSynthesisRequest,
        session_id: Optional[str] = None
    ) -> str:
        """Create a new streaming synthesis task"""
        
        # Check resource limits
        async with self._resource_lock:
            if len(self.active_tasks) >= self.config.max_concurrent_streams:
                raise StreamingError(
                    error_type="resource_limit",
                    error_code="MAX_CONCURRENT_STREAMS_EXCEEDED",
                    message=f"Maximum concurrent streams ({self.config.max_concurrent_streams}) exceeded",
                    timestamp=time.time(),
                    recoverable=True,
                    retry_after=5
                )
        
        # Generate task ID
        task_id = f"stream_{uuid.uuid4().hex[:12]}"
        
        # Create task
        task = StreamingTask(
            task_id=task_id,
            request=request,
            session_id=session_id
        )
        
        # Store task
        async with self._task_lock:
            self.tasks[task_id] = task
            self.active_tasks.add(task_id)
        
        # Update statistics
        async with self._stats_lock:
            self.stats.active_streams += 1
            self.stats.total_sessions += 1
        
        logger.info(f"Created streaming task {task_id} for session {session_id}")
        return task_id
    
    async def start_streaming_task(self, task_id: str) -> AsyncGenerator[bytes, None]:
        """Start streaming synthesis and yield audio chunks"""
        
        async with self._task_lock:
            if task_id not in self.tasks:
                raise StreamingError(
                    error_type="task_not_found",
                    error_code="TASK_NOT_FOUND",
                    message=f"Task {task_id} not found",
                    timestamp=time.time(),
                    recoverable=False
                )
            
            task = self.tasks[task_id]
        
        try:
            # Update task status
            task.status = StreamingTaskStatus.STREAMING
            task.start_time = time.time()
            task.message = "Streaming synthesis started"
            
            # Start streaming synthesis
            chunk_count = 0
            async for chunk_bytes, metadata in self.streaming_engine.stream_cross_lingual_synthesis(task.request):
                # Check if task was cancelled
                if task.cancelled or not self.running:
                    logger.info(f"Task {task_id} was cancelled")
                    break
                
                # Update task progress
                task.chunks_sent += 1
                task.total_bytes += len(chunk_bytes)
                task.last_activity = time.time()
                chunk_count += 1
                
                # Update statistics
                async with self._stats_lock:
                    self.stats.total_chunks_sent += 1
                    self.stats.average_chunk_size = (
                        (self.stats.average_chunk_size * (self.stats.total_chunks_sent - 1) + len(chunk_bytes))
                        / self.stats.total_chunks_sent
                    )
                
                # Yield chunk
                yield chunk_bytes
                
                # Check for final chunk
                if metadata.is_final:
                    break
            
            # Mark task as completed
            task.status = StreamingTaskStatus.COMPLETED
            task.end_time = time.time()
            task.message = f"Streaming completed: {chunk_count} chunks, {task.total_bytes} bytes"
            
            logger.info(f"Streaming task {task_id} completed: {chunk_count} chunks")
            
        except Exception as e:
            # Mark task as failed
            task.status = StreamingTaskStatus.FAILED
            task.end_time = time.time()
            task.error_message = str(e)
            task.message = f"Streaming failed: {str(e)}"
            
            logger.error(f"Streaming task {task_id} failed: {e}")
            raise
        
        finally:
            # Move task from active to completed
            async with self._task_lock:
                if task_id in self.active_tasks:
                    self.active_tasks.remove(task_id)
                    self.completed_tasks.append(task_id)
            
            # Update statistics
            async with self._stats_lock:
                self.stats.active_streams = max(0, self.stats.active_streams - 1)
    
    async def cancel_task(self, task_id: str, reason: str = "User cancelled") -> bool:
        """Cancel a streaming task"""
        async with self._task_lock:
            return await self._cancel_task_internal(task_id, reason)
    
    async def _cancel_task_internal(self, task_id: str, reason: str) -> bool:
        """Internal method to cancel a task"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status in [StreamingTaskStatus.COMPLETED, StreamingTaskStatus.FAILED, StreamingTaskStatus.CANCELLED]:
            return False
        
        # Mark as cancelled
        task.cancelled = True
        task.status = StreamingTaskStatus.CANCELLED
        task.end_time = time.time()
        task.error_message = reason
        task.message = f"Task cancelled: {reason}"
        
        # Signal cancellation
        task.cancel_event.set()
        
        logger.info(f"Cancelled streaming task {task_id}: {reason}")
        return True
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a streaming task"""
        async with self._task_lock:
            if task_id not in self.tasks:
                return None
            
            task = self.tasks[task_id]
            
            # Calculate duration
            duration = None
            if task.start_time:
                end_time = task.end_time or time.time()
                duration = end_time - task.start_time
            
            return {
                "task_id": task.task_id,
                "session_id": task.session_id,
                "status": task.status.value,
                "progress": task.progress,
                "message": task.message,
                "chunks_sent": task.chunks_sent,
                "total_bytes": task.total_bytes,
                "duration": duration,
                "created_at": task.created_at,
                "last_activity": task.last_activity,
                "error_message": task.error_message
            }
    
    async def get_statistics(self) -> StreamingStats:
        """Get current streaming statistics"""
        async with self._stats_lock:
            # Update active counts
            self.stats.active_streams = len(self.active_tasks)
            return self.stats
    
    async def _cleanup_loop(self):
        """Background cleanup loop for completed tasks"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Run cleanup every minute
                await self._cleanup_completed_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_completed_tasks(self):
        """Clean up old completed tasks"""
        current_time = time.time()
        cleanup_threshold = 3600  # Keep completed tasks for 1 hour
        
        async with self._task_lock:
            tasks_to_remove = []
            
            for task_id in self.completed_tasks:
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    if (task.end_time and 
                        current_time - task.end_time > cleanup_threshold):
                        tasks_to_remove.append(task_id)
            
            # Remove old tasks
            for task_id in tasks_to_remove:
                if task_id in self.tasks:
                    del self.tasks[task_id]
                if task_id in self.completed_tasks:
                    self.completed_tasks.remove(task_id)
            
            if tasks_to_remove:
                logger.info(f"Cleaned up {len(tasks_to_remove)} old completed tasks")
    
    async def list_active_tasks(self) -> List[Dict[str, Any]]:
        """List all active streaming tasks"""
        async with self._task_lock:
            active_task_info = []
            for task_id in self.active_tasks:
                if task_id in self.tasks:
                    task_status = await self.get_task_status(task_id)
                    if task_status:
                        active_task_info.append(task_status)
            return active_task_info
