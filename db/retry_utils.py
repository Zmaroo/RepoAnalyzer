"""Database retry utilities.

This module provides comprehensive retry functionality for database operations,
with support for:
1. Exponential backoff with jitter
2. Classification of retryable vs. non-retryable errors
3. Configurable retry parameters
4. Detailed logging of retry attempts
"""

import asyncio
import time
import random
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union, Set
from neo4j.exceptions import Neo4jError, ServiceUnavailable, ClientError
from psycopg.errors import OperationalError as PostgresError
from utils.logger import log
from utils.error_handling import (
    DatabaseError, 
    Neo4jError, 
    TransactionError, 
    handle_async_errors, 
    AsyncErrorBoundary,
    PostgresError,
    ErrorSeverity
)
from utils.async_runner import submit_async_task, get_loop
from utils.shutdown import register_shutdown_handler

# Error classes for retry mechanism
class RetryableError(Exception):
    """Base class for errors that should be retried."""
    pass

class NonRetryableError(Exception):
    """Base class for errors that should not trigger a retry."""
    pass

class RetryableNeo4jError(RetryableError, Neo4jError):
    """Neo4j errors that should trigger a retry."""
    pass

class NonRetryableNeo4jError(NonRetryableError, Neo4jError):
    """Neo4j errors that should not trigger a retry."""
    pass

# Common error patterns to identify retryable vs. non-retryable errors
RETRYABLE_ERROR_PATTERNS = [
    'connection refused', 'timeout', 'timed out', 'temporarily unavailable',
    'deadlock', 'connection reset', 'broken pipe', 'overloaded',
    'too many connections', 'resource temporarily unavailable',
    'connection lost', 'network error', 'server unavailable',
    'service unavailable', 'connection error', 'socket error',
    'connection was reset'
]

NON_RETRYABLE_ERROR_PATTERNS = [
    'syntax error', 'constraint', 'invalid', 'not found', 'already exists',
    'schema', 'authentication', 'authorization', 'permission',
    'type error', 'value error', 'index error', 'out of bounds',
    'null', 'undefined'
]

def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable based on its error message."""
    error_msg = str(error).lower()
    
    # Check if it's explicitly a non-retryable error
    if isinstance(error, NonRetryableError):
        return False
    
    # Check if it's explicitly a retryable error
    if isinstance(error, RetryableError):
        return True
    
    # Check for non-retryable patterns first (they take precedence)
    if any(pattern in error_msg for pattern in NON_RETRYABLE_ERROR_PATTERNS):
        return False
    
    # Check for retryable patterns
    if any(pattern in error_msg for pattern in RETRYABLE_ERROR_PATTERNS):
        return True
    
    # By default, assume Neo4j and TransactionError are retryable
    # unless they contain specific non-retryable patterns
    return isinstance(error, (Neo4jError, TransactionError, ConnectionError, OSError))

def classify_error(error: Exception) -> Exception:
    """Classify an error as retryable or non-retryable."""
    if is_retryable_error(error):
        return RetryableNeo4jError(str(error))
    else:
        return NonRetryableNeo4jError(str(error))

class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter_factor: float = 0.1
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt using exponential backoff with jitter."""
        # Calculate exponential backoff: base_delay * 2^attempt
        delay = self.base_delay * (2 ** attempt)
        
        # Apply maximum delay cap
        delay = min(delay, self.max_delay)
        
        # Apply jitter to avoid thundering herd problem
        jitter = random.uniform(-self.jitter_factor, self.jitter_factor)
        delay = delay * (1 + jitter)
        
        return delay

class DatabaseRetryManager:
    """Manager for database operations with comprehensive retry functionality."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self.config = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise DatabaseError("DatabaseRetryManager not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls, config: RetryConfig = None) -> 'DatabaseRetryManager':
        """Async factory method to create and initialize a DatabaseRetryManager instance."""
        instance = cls()
        instance.config = config or RetryConfig()
        
        try:
            async with AsyncErrorBoundary(
                operation_name="database retry manager initialization",
                error_types=DatabaseError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("database_retry_manager")
                
                instance._initialized = True
                await log("Database retry manager initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing database retry manager: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise DatabaseError(f"Failed to initialize database retry manager: {e}")
    
    async def execute_with_retry(
        self,
        operation_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute an operation with retry logic."""
        if not self._initialized:
            await self.ensure_initialized()
            
        operation_name = kwargs.pop("operation_name", operation_func.__name__)
        retry_count = 0
        total_time = 0
        last_error = None
        
        while retry_count <= self.config.max_retries:
            try:
                task = asyncio.create_task(operation_func(*args, **kwargs))
                self._pending_tasks.add(task)
                try:
                    start_time = time.time()
                    result = await task
                    execution_time = time.time() - start_time
                    total_time += execution_time
                    
                    if retry_count > 0:
                        await log(
                            f"Operation '{operation_name}' succeeded after {retry_count} retries "
                            f"(total time: {total_time:.2f}s)",
                            level="info"
                        )
                    return result
                finally:
                    self._pending_tasks.remove(task)
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if not is_retryable_error(e) or retry_count > self.config.max_retries:
                    break
                
                delay = min(
                    self.config.base_delay * (2 ** (retry_count - 1)),
                    self.config.max_delay
                )
                
                await log(
                    f"Operation '{operation_name}' failed (attempt {retry_count}/{self.config.max_retries}). "
                    f"Error: {str(e)}. Retrying in {delay:.2f}s...",
                    level="warning"
                )
                
                await asyncio.sleep(delay)
                total_time += delay
        
        error_msg = (
            f"Operation '{operation_name}' failed after {self.config.max_retries} retries "
            f"(total time: {total_time:.2f}s). Last error: {str(last_error)}"
        )
        await log(error_msg, level="error")
        raise DatabaseError(error_msg)
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("database_retry_manager")
            
            self._initialized = False
            await log("Database retry manager cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up database retry manager: {e}", level="error")
            raise DatabaseError(f"Failed to cleanup database retry manager: {e}")

# Default retry manager instance
default_retry_manager = None

async def get_retry_manager() -> DatabaseRetryManager:
    """Get the default retry manager instance."""
    global default_retry_manager
    if not default_retry_manager:
        default_retry_manager = await DatabaseRetryManager.create()
    return default_retry_manager

# Register cleanup handler
async def cleanup_retry():
    """Cleanup retry utilities resources."""
    try:
        if default_retry_manager:
            await default_retry_manager.cleanup()
        await log("Retry utilities cleaned up", level="info")
    except Exception as e:
        await log(f"Error cleaning up retry utilities: {e}", level="error")
        raise DatabaseError(f"Failed to cleanup retry utilities: {e}")

def with_retry(
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None
):
    """Decorator for retrying operations with custom retry parameters."""
    return default_retry_manager.retry(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay
    ) 