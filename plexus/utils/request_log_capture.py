"""
Request-scoped log capture utilities for FastAPI applications.

This module provides several approaches to capture logs per request:
1. MemoryHandler - Buffers logs and flushes on completion
2. StringIO handler - Captures logs to a string buffer
3. Context variable approach - Tracks logs per request context
"""

import logging
import threading
import contextvars
from collections import deque
from io import StringIO
from typing import List, Optional, Dict
from datetime import datetime, timezone
import uuid
import io
from contextlib import contextmanager
import asyncio

# Context variable to track the current request ID
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('request_id', default='')

class RequestLogCapture:
    """
    Captures logs for a specific request using various methods.
    """
    
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.request_id = str(uuid.uuid4())
        self.logs: List[str] = []
        self.start_time = datetime.now(timezone.utc)
        
    def __enter__(self):
        # Set the request ID in context
        request_id_var.set(self.request_id)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up context
        try:
            request_id_var.set('')
        except LookupError:
            pass



class RingBufferLogHandler(logging.Handler):
    """
    Log handler that maintains a ring buffer of recent log messages.
    Similar to spdlog's backtrace feature.
    """
    
    def __init__(self, capacity: int = 100):
        super().__init__()
        self.log_buffer = deque(maxlen=capacity)
        self.lock = threading.Lock()
        
    def emit(self, record):
        with self.lock:
            try:
                msg = self.format(record)
                timestamp = datetime.now(timezone.utc).isoformat()
                self.log_buffer.append(f"{timestamp} - {msg}")
            except Exception:
                self.handleError(record)
    
    def get_recent_logs(self) -> List[str]:
        """Get all logs from the ring buffer."""
        with self.lock:
            return list(self.log_buffer)
    
    def clear(self):
        """Clear the ring buffer."""
        with self.lock:
            self.log_buffer.clear()



class BufferingLogHandler(logging.Handler):
    """
    Handler that buffers logs in memory and can flush them conditionally.
    Based on Python's MemoryHandler but with more control.
    """
    
    def __init__(self, capacity: int = 50, target_handler: Optional[logging.Handler] = None):
        super().__init__()
        self.capacity = capacity
        self.buffer: List[logging.LogRecord] = []
        self.target_handler = target_handler
        self.lock = threading.Lock()
        
    def emit(self, record):
        with self.lock:
            if len(self.buffer) >= self.capacity:
                self.buffer.pop(0)  # Remove oldest record
            self.buffer.append(record)
    
    def flush_to_target(self):
        """Flush buffered records to target handler."""
        if not self.target_handler:
            return
            
        with self.lock:
            for record in self.buffer:
                self.target_handler.handle(record)
    
    def get_buffered_logs(self) -> List[str]:
        """Get formatted logs from buffer."""
        with self.lock:
            return [self.format(record) for record in self.buffer]
    
    def clear_buffer(self):
        """Clear the buffer."""
        with self.lock:
            self.buffer.clear()

def setup_request_logging(logger_name: str = None) -> logging.Logger:
    """
    Set up a logger with request-scoped capturing capabilities.
    Note: This function is deprecated. Use RequestLogManager directly instead.
    
    Args:
        logger_name: Name of the logger, defaults to calling module
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name or __name__)
    
    # Set up formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Add a console handler for normal logging
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.setLevel(logging.INFO)
    
    return logger

# Example usage patterns

class SimpleRequestLogCapture:
    """
    Simple request-scoped log capture that doesn't interfere with existing logging.
    Uses a memory handler approach to capture logs without modifying the root logger.
    """
    
    def __init__(self):
        self._handlers: Dict[str, logging.Handler] = {}
        self._original_handlers: List[logging.Handler] = []
        
    def start_request_capture(self, request_id: str = None) -> str:
        """
        Start capturing logs for a request using a memory buffer approach.
        
        Args:
            request_id: Optional request ID, generates UUID if not provided
            
        Returns:
            The request ID being used
        """
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Create a memory handler that buffers logs
        memory_handler = MemoryLogHandler(capacity=1000)
        memory_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        
        # Store the handler
        self._handlers[request_id] = memory_handler
        
        # Add to root logger temporarily
        root_logger = logging.getLogger()
        root_logger.addHandler(memory_handler)
        
        return request_id
    
    def get_request_logs(self, request_id: str) -> str:
        """
        Get captured logs for a specific request.
        
        Args:
            request_id: The request ID to get logs for
            
        Returns:
            Captured logs as a string
        """
        handler = self._handlers.get(request_id)
        if handler and hasattr(handler, 'get_logs'):
            return handler.get_logs()
        return ""
    
    def finish_request_capture(self, request_id: str) -> str:
        """
        Finish capturing logs for a request and clean up.
        
        Args:
            request_id: The request ID to finish
            
        Returns:
            Final captured logs
        """
        handler = self._handlers.get(request_id)
        if not handler:
            return ""
        
        # Get final logs
        logs = handler.get_logs() if hasattr(handler, 'get_logs') else ""
        
        # Clean up - remove from root logger
        root_logger = logging.getLogger()
        root_logger.removeHandler(handler)
        
        # Close and remove from our tracking
        handler.close()
        del self._handlers[request_id]
        
        return logs

class MemoryLogHandler(logging.Handler):
    """
    Simple memory-based log handler that captures all logs to a string buffer.
    This doesn't filter by request ID, it just captures everything during its lifetime.
    """
    
    def __init__(self, capacity: int = 1000):
        super().__init__()
        self.capacity = capacity
        self.log_buffer = StringIO()
        self.lock = threading.Lock()
        self.record_count = 0
        
    def emit(self, record):
        if self.record_count >= self.capacity:
            return  # Don't capture more than capacity
            
        with self.lock:
            try:
                msg = self.format(record)
                self.log_buffer.write(msg + '\n')
                self.record_count += 1
            except Exception:
                self.handleError(record)
    
    def get_logs(self) -> str:
        """Get all captured logs as a string."""
        with self.lock:
            return self.log_buffer.getvalue()
    
    def close(self):
        with self.lock:
            self.log_buffer.close()
        super().close()

class RequestLogManager:
    """
    High-level manager for request-scoped log capture.
    Now uses the simpler approach that doesn't interfere with existing logging.
    """
    
    def __init__(self, logger_name: str = None, buffer_size: int = 100):
        self.capture = SimpleRequestLogCapture()
        
    def start_request_capture(self, request_id: str = None) -> str:
        """Start capturing logs for a request."""
        return self.capture.start_request_capture(request_id)
    
    def get_request_logs(self, request_id: str) -> str:
        """Get captured logs for a specific request."""
        return self.capture.get_request_logs(request_id)
    
    def finish_request_capture(self, request_id: str) -> str:
        """Finish capturing logs for a request and clean up."""
        return self.capture.finish_request_capture(request_id)

# Global instance for easy access
_global_log_manager = RequestLogManager()

def start_request_logging(request_id: str = None) -> str:
    """Global function to start request logging."""
    return _global_log_manager.start_request_capture(request_id)

def get_request_logs(request_id: str) -> str:
    """Global function to get request logs."""
    return _global_log_manager.get_request_logs(request_id)

def finish_request_logging(request_id: str) -> str:
    """Global function to finish request logging."""
    return _global_log_manager.finish_request_capture(request_id)

class ThreadLocalLogCapture:
    """
    Thread-safe log capture that uses thread-local storage to avoid conflicts
    between concurrent requests.
    """
    def __init__(self):
        self._local = threading.local()
        self._handlers = {}
    
    def start_capture(self, request_id: str, level=logging.INFO):
        """Start capturing logs for a specific request"""
        # Create a StringIO buffer for this request
        buffer = io.StringIO()
        
        # Create a custom handler that prints logger names for debugging
        class DebugStreamHandler(logging.StreamHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._in_emit = False
                
            def emit(self, record):
                # Prevent recursion
                if self._in_emit:
                    return
                    
                self._in_emit = True
                try:
                    # Skip messages from log capture itself to prevent recursion
                    if '[LOG_CAPTURE_DEBUG]' not in record.getMessage():
                        # Print which logger is emitting (skip noisy loggers)
                        if record.name not in ['urllib3', 'botocore', 'boto3', 'gql.transport', 'gql.dsl']:
                            print(f"[LOG_CAPTURE_DEBUG] Logger '{record.name}' emitting: {record.getMessage()[:100]}...")
                    
                    super().emit(record)
                except Exception:
                    self.handleError(record)
                finally:
                    self._in_emit = False
        
        handler = DebugStreamHandler(buffer)
        handler.setLevel(level)
        
        # Use a simple format to avoid recursion
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        # Store in thread-local storage
        if not hasattr(self._local, 'captures'):
            self._local.captures = {}
        self._local.captures[request_id] = {
            'buffer': buffer,
            'handler': handler,
            'original_handlers': []
        }
        
        # Add handler to specific loggers
        target_loggers = [
            '',  # The root logger (empty string name) - this is what most logs go through
            'plexus',
            'plexus.api',
            'plexus/api',  # Added slash version
            'plexus.scores',
            'plexus.CustomLogging',
            'plexus.dashboard',
            'Call-Criteria-Python',
            '__main__'  # In case any logs use the main module logger
        ]
        
        for logger_name in target_loggers:
            logger = logging.getLogger(logger_name)
            logger.addHandler(handler)
            self._local.captures[request_id]['original_handlers'].append((logger, handler))
            # Debug: print which loggers we're attaching to
            actual_name = logger.name if logger.name else '<root>'
            print(f"[LOG_CAPTURE_DEBUG] Attached handler to logger: '{logger_name}' (actual name: '{actual_name}')")
    
    def get_logs(self, request_id: str) -> Optional[str]:
        """Get captured logs for a request"""
        if hasattr(self._local, 'captures') and request_id in self._local.captures:
            buffer = self._local.captures[request_id]['buffer']
            content = buffer.getvalue()
            # Debug output
            if request_id:
                print(f"[LOG_CAPTURE_DEBUG] get_logs({request_id}): buffer has {len(content) if content else 0} bytes")
            return content
        print(f"[LOG_CAPTURE_DEBUG] get_logs({request_id}): No capture found for this request_id")
        return None
    
    def stop_capture(self, request_id: str):
        """Stop capturing logs for a request and clean up"""
        if hasattr(self._local, 'captures') and request_id in self._local.captures:
            capture = self._local.captures[request_id]
            
            # Remove handlers
            for logger, handler in capture['original_handlers']:
                logger.removeHandler(handler)
            
            # Close buffer
            capture['buffer'].close()
            
            # Clean up
            del self._local.captures[request_id]


# Global instance for thread-local log capture
_log_capture = ThreadLocalLogCapture()


@contextmanager
def capture_request_logs(request_id: Optional[str] = None):
    """
    Context manager to capture logs for a specific request.
    
    Usage:
        with capture_request_logs() as (request_id, get_logs):
            # Do work that generates logs
            logs = get_logs()
    """
    if request_id is None:
        request_id = str(uuid.uuid4())
    
    # Start capture
    _log_capture.start_capture(request_id)
    
    def get_logs():
        return _log_capture.get_logs(request_id)
    
    try:
        yield (request_id, get_logs)
    finally:
        # Stop capture
        _log_capture.stop_capture(request_id)


class AsyncLogCapture:
    """
    Async-friendly log capture that works with FastAPI
    """
    def __init__(self):
        self.active_captures = {}
        self.lock = asyncio.Lock()
    
    async def capture_logs_async(self, request_id: str, coro):
        """
        Capture logs during the execution of an async coroutine
        """
        # Use the thread-local capture in the async context
        _log_capture.start_capture(request_id)
        
        try:
            # Execute the coroutine
            result = await coro
            
            # Get the captured logs
            logs = _log_capture.get_logs(request_id)
            
            return result, logs
        finally:
            # Clean up
            _log_capture.stop_capture(request_id) 