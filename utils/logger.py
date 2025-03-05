"""Enhanced logging system with error handling."""

import logging
import sys
import os
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Set
import json
from utils.error_handling import (
    handle_async_errors,
    LoggingError,
    AsyncErrorBoundary,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler

class EnhancedLogger:
    """Enhanced logging with structured output and error handling."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._log_queue = asyncio.Queue()
        self._is_running = False
        self._task = None
        self.log_levels = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL
        }
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise LoggingError("EnhancedLogger not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'EnhancedLogger':
        """Async factory method to create and initialize an EnhancedLogger instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="logger initialization",
                error_types=LoggingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize logging configuration
                instance._initialize_logger()
                
                # Start log processing task
                instance._is_running = True
                instance._task = asyncio.create_task(instance._process_logs())
                instance._pending_tasks.add(instance._task)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("enhanced_logger")
                
                instance._initialized = True
                # Use direct logging here to avoid circular dependency
                logging.info("Enhanced logger initialized")
                return instance
        except Exception as e:
            # Use direct logging here to avoid circular dependency
            logging.error(f"Error initializing enhanced logger: {e}")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise LoggingError(f"Failed to initialize enhanced logger: {e}")
    
    def _initialize_logger(self):
        """Initialize logging configuration."""
        try:
            # Create logs directory if it doesn't exist
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Set up file handler
            log_file = os.path.join(
                log_dir,
                f"app_{datetime.now().strftime('%Y%m%d')}.log"
            )
            
            # Configure logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler(sys.stdout)
                ]
            )
        except Exception as e:
            print(f"Error initializing logger: {e}")
    
    async def _process_logs(self):
        """Process logs from the queue."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            while self._is_running:
                try:
                    # Get log entry from queue with timeout
                    log_entry = await asyncio.wait_for(self._log_queue.get(), timeout=1.0)
                    await self._write_log(log_entry)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"Error processing log entry: {e}")
        except asyncio.CancelledError:
            # Process remaining logs before exiting
            while not self._log_queue.empty():
                try:
                    log_entry = await asyncio.wait_for(self._log_queue.get(), timeout=1.0)
                    await self._write_log(log_entry)
                except (asyncio.TimeoutError, Exception):
                    break
    
    async def _write_log(self, log_entry: Dict[str, Any]):
        """Write a log entry to all handlers."""
        try:
            level = self.log_levels.get(log_entry.get('level', 'info'), logging.INFO)
            message = json.dumps(log_entry)
            logging.log(level, message)
        except Exception as e:
            print(f"Error writing log entry: {e}")
    
    @handle_async_errors(error_types=LoggingError)
    async def log(
        self,
        message: str,
        level: str = "info",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a message with optional context."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with self._lock:
            try:
                # Create structured log entry
                log_entry = {
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                    "level": level
                }
                
                if context:
                    log_entry["context"] = context
                
                # Add to queue
                task = asyncio.create_task(self._log_queue.put(log_entry))
                self._pending_tasks.add(task)
                try:
                    await task
                finally:
                    self._pending_tasks.remove(task)
            except Exception as e:
                print(f"Error queueing log message: {e}")
    
    async def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message."""
        await self.log(message, "debug", context)
    
    async def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log info message."""
        await self.log(message, "info", context)
    
    async def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message."""
        await self.log(message, "warning", context)
    
    async def error(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log error message."""
        await self.log(message, "error", context)
    
    async def critical(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log critical message."""
        await self.log(message, "critical", context)
    
    async def cleanup(self) -> None:
        """Clean up logger resources."""
        try:
            if not self._initialized:
                return
                
            # Stop log processing
            self._is_running = False
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Process remaining logs
            while not self._log_queue.empty():
                try:
                    log_entry = await asyncio.wait_for(self._log_queue.get(), timeout=1.0)
                    await self._write_log(log_entry)
                except asyncio.TimeoutError:
                    break
                except Exception as e:
                    print(f"Error processing remaining logs: {e}")
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("enhanced_logger")
            
            self._initialized = False
            # Use direct logging here to avoid circular dependency
            logging.info("Enhanced logger cleaned up")
        except Exception as e:
            # Use direct logging here to avoid circular dependency
            logging.error(f"Error cleaning up enhanced logger: {e}")
            raise LoggingError(f"Failed to cleanup enhanced logger: {e}")

# Global logger instance
logger = None

async def get_logger() -> EnhancedLogger:
    """Get the global logger instance."""
    global logger
    if not logger:
        logger = await EnhancedLogger.create()
    return logger

# Convenience function
async def log(message: str, level: str = "info", context: Optional[Dict[str, Any]] = None):
    """Global logging function."""
    global logger
    if not logger:
        logger = await get_logger()
    await logger.log(message, level, context)

# Synchronous convenience function for backward compatibility
def log_sync(message: str, level: str = "info", context: Optional[Dict[str, Any]] = None):
    """Synchronous global logging function."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(log(message, level, context))