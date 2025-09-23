"""Comprehensive Error Handling for Streaming Scenarios"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable, List
from enum import Enum
from dataclasses import dataclass
from contextlib import asynccontextmanager

from app.models.streaming import StreamingError

logger = logging.getLogger(__name__)

class StreamingErrorType(str, Enum):
    """Types of streaming errors"""
    CONNECTION_ERROR = "connection_error"
    SYNTHESIS_ERROR = "synthesis_error"
    ENCODING_ERROR = "encoding_error"
    RESOURCE_ERROR = "resource_error"
    TIMEOUT_ERROR = "timeout_error"
    CANCELLATION_ERROR = "cancellation_error"
    VALIDATION_ERROR = "validation_error"
    NETWORK_ERROR = "network_error"

class ErrorSeverity(str, Enum):
    """Error severity levels"""
    LOW = "low"           # Minor issues, can continue
    MEDIUM = "medium"     # Significant issues, may need retry
    HIGH = "high"         # Critical issues, should stop streaming
    CRITICAL = "critical" # System-level issues, needs immediate attention

@dataclass
class ErrorContext:
    """Context information for error handling"""
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    request_id: Optional[str] = None
    chunk_index: Optional[int] = None
    client_info: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

class StreamingErrorHandler:
    """Comprehensive error handler for streaming scenarios"""
    
    def __init__(self):
        self.error_handlers: Dict[StreamingErrorType, Callable] = {
            StreamingErrorType.CONNECTION_ERROR: self._handle_connection_error,
            StreamingErrorType.SYNTHESIS_ERROR: self._handle_synthesis_error,
            StreamingErrorType.ENCODING_ERROR: self._handle_encoding_error,
            StreamingErrorType.RESOURCE_ERROR: self._handle_resource_error,
            StreamingErrorType.TIMEOUT_ERROR: self._handle_timeout_error,
            StreamingErrorType.CANCELLATION_ERROR: self._handle_cancellation_error,
            StreamingErrorType.VALIDATION_ERROR: self._handle_validation_error,
            StreamingErrorType.NETWORK_ERROR: self._handle_network_error,
        }
        
        # Error statistics
        self.error_counts: Dict[StreamingErrorType, int] = {
            error_type: 0 for error_type in StreamingErrorType
        }
        self.total_errors = 0
        self.error_rate_window = []  # For calculating error rate
        self.max_window_size = 1000
        
        # Recovery strategies
        self.recovery_strategies = {
            StreamingErrorType.CONNECTION_ERROR: self._recover_connection,
            StreamingErrorType.SYNTHESIS_ERROR: self._recover_synthesis,
            StreamingErrorType.ENCODING_ERROR: self._recover_encoding,
            StreamingErrorType.RESOURCE_ERROR: self._recover_resource,
            StreamingErrorType.TIMEOUT_ERROR: self._recover_timeout,
            StreamingErrorType.NETWORK_ERROR: self._recover_network,
        }
    
    async def handle_error(
        self, 
        error: Exception, 
        context: ErrorContext,
        error_type: Optional[StreamingErrorType] = None
    ) -> StreamingError:
        """Handle streaming error with appropriate strategy"""
        
        # Determine error type if not provided
        if error_type is None:
            error_type = self._classify_error(error)
        
        # Update statistics
        self._update_error_stats(error_type)
        
        # Get severity
        severity = self._get_error_severity(error_type, error)
        
        # Create streaming error
        streaming_error = StreamingError(
            error_type=error_type.value,
            error_code=self._get_error_code(error_type, error),
            message=str(error),
            session_id=context.session_id,
            request_id=context.request_id,
            timestamp=context.timestamp,
            recoverable=self._is_recoverable(error_type, severity),
            retry_after=self._get_retry_delay(error_type, severity)
        )
        
        # Log error
        log_level = self._get_log_level(severity)
        logger.log(
            log_level,
            f"Streaming error [{error_type.value}]: {str(error)} "
            f"(session: {context.session_id}, severity: {severity.value})"
        )
        
        # Handle error with specific handler
        handler = self.error_handlers.get(error_type, self._handle_generic_error)
        await handler(error, context, streaming_error)
        
        return streaming_error
    
    def _classify_error(self, error: Exception) -> StreamingErrorType:
        """Classify error type based on exception"""
        
        error_name = type(error).__name__.lower()
        error_message = str(error).lower()
        
        # Connection-related errors
        if any(keyword in error_name for keyword in ['connection', 'disconnect', 'websocket']):
            return StreamingErrorType.CONNECTION_ERROR
        
        # Network-related errors
        if any(keyword in error_name for keyword in ['network', 'socket', 'timeout']):
            return StreamingErrorType.NETWORK_ERROR
        
        # Synthesis-related errors
        if any(keyword in error_message for keyword in ['synthesis', 'model', 'inference']):
            return StreamingErrorType.SYNTHESIS_ERROR
        
        # Encoding-related errors
        if any(keyword in error_message for keyword in ['encoding', 'format', 'audio']):
            return StreamingErrorType.ENCODING_ERROR
        
        # Resource-related errors
        if any(keyword in error_name for keyword in ['memory', 'resource', 'limit']):
            return StreamingErrorType.RESOURCE_ERROR
        
        # Timeout errors
        if 'timeout' in error_name or 'timeout' in error_message:
            return StreamingErrorType.TIMEOUT_ERROR
        
        # Cancellation errors
        if any(keyword in error_name for keyword in ['cancel', 'abort']):
            return StreamingErrorType.CANCELLATION_ERROR
        
        # Validation errors
        if any(keyword in error_name for keyword in ['validation', 'value', 'type']):
            return StreamingErrorType.VALIDATION_ERROR
        
        # Default to synthesis error
        return StreamingErrorType.SYNTHESIS_ERROR
    
    def _get_error_severity(self, error_type: StreamingErrorType, error: Exception) -> ErrorSeverity:
        """Determine error severity"""
        
        severity_map = {
            StreamingErrorType.CONNECTION_ERROR: ErrorSeverity.HIGH,
            StreamingErrorType.SYNTHESIS_ERROR: ErrorSeverity.MEDIUM,
            StreamingErrorType.ENCODING_ERROR: ErrorSeverity.MEDIUM,
            StreamingErrorType.RESOURCE_ERROR: ErrorSeverity.HIGH,
            StreamingErrorType.TIMEOUT_ERROR: ErrorSeverity.MEDIUM,
            StreamingErrorType.CANCELLATION_ERROR: ErrorSeverity.LOW,
            StreamingErrorType.VALIDATION_ERROR: ErrorSeverity.MEDIUM,
            StreamingErrorType.NETWORK_ERROR: ErrorSeverity.HIGH,
        }
        
        return severity_map.get(error_type, ErrorSeverity.MEDIUM)
    
    def _get_error_code(self, error_type: StreamingErrorType, error: Exception) -> str:
        """Generate error code"""
        
        base_codes = {
            StreamingErrorType.CONNECTION_ERROR: "CONN",
            StreamingErrorType.SYNTHESIS_ERROR: "SYNTH",
            StreamingErrorType.ENCODING_ERROR: "ENC",
            StreamingErrorType.RESOURCE_ERROR: "RES",
            StreamingErrorType.TIMEOUT_ERROR: "TIMEOUT",
            StreamingErrorType.CANCELLATION_ERROR: "CANCEL",
            StreamingErrorType.VALIDATION_ERROR: "VAL",
            StreamingErrorType.NETWORK_ERROR: "NET",
        }
        
        base_code = base_codes.get(error_type, "UNKNOWN")
        error_name = type(error).__name__.upper()
        
        return f"{base_code}_{error_name}"
    
    def _is_recoverable(self, error_type: StreamingErrorType, severity: ErrorSeverity) -> bool:
        """Determine if error is recoverable"""
        
        # Critical errors are generally not recoverable
        if severity == ErrorSeverity.CRITICAL:
            return False
        
        # Some error types are inherently recoverable
        recoverable_types = {
            StreamingErrorType.TIMEOUT_ERROR,
            StreamingErrorType.NETWORK_ERROR,
            StreamingErrorType.ENCODING_ERROR,
        }
        
        return error_type in recoverable_types or severity in [ErrorSeverity.LOW, ErrorSeverity.MEDIUM]
    
    def _get_retry_delay(self, error_type: StreamingErrorType, severity: ErrorSeverity) -> Optional[int]:
        """Get retry delay in seconds"""
        
        if severity == ErrorSeverity.CRITICAL:
            return None  # No retry for critical errors
        
        delay_map = {
            ErrorSeverity.LOW: 1,
            ErrorSeverity.MEDIUM: 5,
            ErrorSeverity.HIGH: 15,
        }
        
        return delay_map.get(severity, 5)
    
    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """Get logging level for severity"""
        
        level_map = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }
        
        return level_map.get(severity, logging.WARNING)
    
    def _update_error_stats(self, error_type: StreamingErrorType):
        """Update error statistics"""
        
        self.error_counts[error_type] += 1
        self.total_errors += 1
        
        # Update error rate window
        current_time = time.time()
        self.error_rate_window.append(current_time)
        
        # Keep window size manageable
        if len(self.error_rate_window) > self.max_window_size:
            self.error_rate_window = self.error_rate_window[-self.max_window_size:]
    
    # Error-specific handlers
    async def _handle_connection_error(self, error: Exception, context: ErrorContext, streaming_error: StreamingError):
        """Handle connection errors"""
        logger.warning(f"Connection error in session {context.session_id}: {error}")
        # Connection errors usually mean the client disconnected
        # No specific action needed, just log and return
    
    async def _handle_synthesis_error(self, error: Exception, context: ErrorContext, streaming_error: StreamingError):
        """Handle synthesis errors"""
        logger.error(f"Synthesis error in session {context.session_id}: {error}")
        # Could implement fallback synthesis methods here
    
    async def _handle_encoding_error(self, error: Exception, context: ErrorContext, streaming_error: StreamingError):
        """Handle encoding errors"""
        logger.warning(f"Encoding error in session {context.session_id}: {error}")
        # Could implement format fallback here
    
    async def _handle_resource_error(self, error: Exception, context: ErrorContext, streaming_error: StreamingError):
        """Handle resource errors"""
        logger.error(f"Resource error in session {context.session_id}: {error}")
        # Could implement resource cleanup here
    
    async def _handle_timeout_error(self, error: Exception, context: ErrorContext, streaming_error: StreamingError):
        """Handle timeout errors"""
        logger.warning(f"Timeout error in session {context.session_id}: {error}")
        # Timeout errors are often recoverable with retry
    
    async def _handle_cancellation_error(self, error: Exception, context: ErrorContext, streaming_error: StreamingError):
        """Handle cancellation errors"""
        logger.info(f"Cancellation in session {context.session_id}: {error}")
        # Cancellation is normal, just log
    
    async def _handle_validation_error(self, error: Exception, context: ErrorContext, streaming_error: StreamingError):
        """Handle validation errors"""
        logger.warning(f"Validation error in session {context.session_id}: {error}")
        # Validation errors indicate client-side issues
    
    async def _handle_network_error(self, error: Exception, context: ErrorContext, streaming_error: StreamingError):
        """Handle network errors"""
        logger.warning(f"Network error in session {context.session_id}: {error}")
        # Network errors are often temporary
    
    async def _handle_generic_error(self, error: Exception, context: ErrorContext, streaming_error: StreamingError):
        """Handle generic/unknown errors"""
        logger.error(f"Unknown error in session {context.session_id}: {error}")
    
    # Recovery strategies
    async def _recover_connection(self, error: Exception, context: ErrorContext) -> bool:
        """Attempt to recover from connection error"""
        # Connection recovery is usually not possible in streaming
        return False
    
    async def _recover_synthesis(self, error: Exception, context: ErrorContext) -> bool:
        """Attempt to recover from synthesis error"""
        # Could implement model reload or fallback here
        return False
    
    async def _recover_encoding(self, error: Exception, context: ErrorContext) -> bool:
        """Attempt to recover from encoding error"""
        # Could implement format fallback here
        return True
    
    async def _recover_resource(self, error: Exception, context: ErrorContext) -> bool:
        """Attempt to recover from resource error"""
        # Could implement resource cleanup here
        return False
    
    async def _recover_timeout(self, error: Exception, context: ErrorContext) -> bool:
        """Attempt to recover from timeout error"""
        # Timeout recovery often involves retry
        return True
    
    async def _recover_network(self, error: Exception, context: ErrorContext) -> bool:
        """Attempt to recover from network error"""
        # Network errors are often temporary
        return True
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics"""
        
        # Calculate error rate (errors per minute)
        current_time = time.time()
        recent_errors = [t for t in self.error_rate_window if current_time - t < 60]
        error_rate = len(recent_errors)
        
        return {
            "total_errors": self.total_errors,
            "error_counts": dict(self.error_counts),
            "error_rate_per_minute": error_rate,
            "most_common_error": max(self.error_counts, key=self.error_counts.get) if self.error_counts else None
        }

@asynccontextmanager
async def streaming_error_context(
    error_handler: StreamingErrorHandler,
    context: ErrorContext,
    error_type: Optional[StreamingErrorType] = None
):
    """Context manager for handling streaming errors"""
    
    try:
        yield
    except Exception as e:
        streaming_error = await error_handler.handle_error(e, context, error_type)
        raise streaming_error from e
