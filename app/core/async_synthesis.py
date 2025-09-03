"""
Async voice synthesis system for CosyVoice2 API
Handles background voice generation tasks
"""

import asyncio
import uuid
import time
import logging
from typing import Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from app.models.synthesis import SynthesisResponse, AudioFormat
from app.core.synthesis_engine import SynthesisEngine

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SynthesisTask:
    """Synthesis task data structure"""
    task_id: str
    status: TaskStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[SynthesisResponse] = None
    error: Optional[str] = None
    progress: float = 0.0


class AsyncSynthesisManager:
    """Manages async voice synthesis tasks"""
    
    def __init__(self, synthesis_engine: SynthesisEngine, max_workers: int = 4):
        self.synthesis_engine = synthesis_engine
        self.tasks: Dict[str, SynthesisTask] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._cleanup_interval = 3600  # 1 hour
        self._max_task_age = 7200  # 2 hours
        self._cleanup_task = None
        
    async def start(self):
        """Start the async synthesis manager"""
        logger.info("Starting async synthesis manager...")
        self._cleanup_task = asyncio.create_task(self._cleanup_old_tasks())
        
    async def stop(self):
        """Stop the async synthesis manager"""
        logger.info("Stopping async synthesis manager...")
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self.executor.shutdown(wait=True)
        
    def generate_task_id(self) -> str:
        """Generate unique task ID"""
        return f"task_{uuid.uuid4().hex[:12]}"
    
    async def submit_sft_task(self, request) -> str:
        """Submit SFT synthesis task"""
        task_id = self.generate_task_id()
        task = SynthesisTask(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=time.time()
        )
        self.tasks[task_id] = task
        
        # Start background task
        asyncio.create_task(self._process_sft_task(task_id, request))
        
        logger.info(f"Submitted SFT synthesis task: {task_id}")
        return task_id
    
    async def submit_zero_shot_task(self, request, prompt_audio: Optional[bytes] = None) -> str:
        """Submit zero-shot synthesis task"""
        task_id = self.generate_task_id()
        task = SynthesisTask(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=time.time()
        )
        self.tasks[task_id] = task
        
        # Start background task
        asyncio.create_task(self._process_zero_shot_task(task_id, request, prompt_audio))
        
        logger.info(f"Submitted zero-shot synthesis task: {task_id}")
        return task_id
    
    async def submit_cross_lingual_task(self, request, prompt_audio: Optional[bytes] = None) -> str:
        """Submit cross-lingual synthesis task"""
        task_id = self.generate_task_id()
        task = SynthesisTask(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=time.time()
        )
        self.tasks[task_id] = task
        
        # Start background task
        asyncio.create_task(self._process_cross_lingual_task(task_id, request, prompt_audio))
        
        logger.info(f"Submitted cross-lingual synthesis task: {task_id}")
        return task_id
    
    async def submit_instruct_task(self, request) -> str:
        """Submit instruct synthesis task"""
        task_id = self.generate_task_id()
        task = SynthesisTask(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=time.time()
        )
        self.tasks[task_id] = task
        
        # Start background task
        asyncio.create_task(self._process_instruct_task(task_id, request))
        
        logger.info(f"Submitted instruct synthesis task: {task_id}")
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[SynthesisTask]:
        """Get task status"""
        return self.tasks.get(task_id)
    
    async def get_task_result(self, task_id: str) -> Optional[SynthesisResponse]:
        """Get task result if completed"""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.COMPLETED:
            return task.result
        return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.FAILED
            task.error = "Task cancelled by user"
            task.completed_at = time.time()
            return True
        return False
    
    async def list_tasks(self, limit: int = 50) -> list[SynthesisTask]:
        """List recent tasks"""
        tasks = list(self.tasks.values())
        tasks.sort(key=lambda x: x.created_at, reverse=True)
        return tasks[:limit]
    
    async def _process_sft_task(self, task_id: str, request):
        """Process SFT synthesis task in background"""
        task = self.tasks[task_id]
        try:
            task.status = TaskStatus.PROCESSING
            task.started_at = time.time()
            task.progress = 0.1
            
            # Run synthesis directly (it's already async)
            result = await self.synthesis_engine.synthesize_sft(request)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.completed_at = time.time()
            
            logger.info(f"SFT synthesis task {task_id} completed successfully")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            logger.error(f"SFT synthesis task {task_id} failed: {e}")
    
    async def _process_zero_shot_task(self, task_id: str, request, prompt_audio: Optional[bytes]):
        """Process zero-shot synthesis task in background"""
        task = self.tasks[task_id]
        try:
            task.status = TaskStatus.PROCESSING
            task.started_at = time.time()
            task.progress = 0.1
            
            # Run synthesis directly (it's already async)
            result = await self.synthesis_engine.synthesize_zero_shot(request, prompt_audio)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.completed_at = time.time()
            
            logger.info(f"Zero-shot synthesis task {task_id} completed successfully")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            logger.error(f"Zero-shot synthesis task {task_id} failed: {e}")
    
    async def _process_cross_lingual_task(self, task_id: str, request, prompt_audio: Optional[bytes]):
        """Process cross-lingual synthesis task in background"""
        task = self.tasks[task_id]
        try:
            task.status = TaskStatus.PROCESSING
            task.started_at = time.time()
            task.progress = 0.1
            
            # Run synthesis directly (it's already async)
            result = await self.synthesis_engine.synthesize_cross_lingual(request, prompt_audio)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.completed_at = time.time()
            
            logger.info(f"Cross-lingual synthesis task {task_id} completed successfully")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            logger.error(f"Cross-lingual synthesis task {task_id} failed: {e}")
    
    async def _process_instruct_task(self, task_id: str, request):
        """Process instruct synthesis task in background"""
        task = self.tasks[task_id]
        try:
            task.status = TaskStatus.PROCESSING
            task.started_at = time.time()
            task.progress = 0.1
            
            # Run synthesis directly (it's already async)
            result = await self.synthesis_engine.synthesize_instruct(request)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.completed_at = time.time()
            
            logger.info(f"Instruct synthesis task {task_id} completed successfully")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            logger.error(f"Instruct synthesis task {task_id} failed: {e}")
    
    async def _cleanup_old_tasks(self):
        """Cleanup old completed tasks periodically"""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                current_time = time.time()
                
                # Remove old tasks
                tasks_to_remove = []
                for task_id, task in self.tasks.items():
                    if (current_time - task.created_at) > self._max_task_age:
                        tasks_to_remove.append(task_id)
                
                for task_id in tasks_to_remove:
                    del self.tasks[task_id]
                
                if tasks_to_remove:
                    logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in task cleanup: {e}")


# Global async synthesis manager instance
async_synthesis_manager: Optional[AsyncSynthesisManager] = None
