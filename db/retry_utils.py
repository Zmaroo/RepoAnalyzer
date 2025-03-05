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
    ErrorBoundary,
    PostgresError,
    ErrorSeverity
)
from utils.async_runner import submit_async_task, get_loop
from utils.app_init import register_shutdown_handler

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
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self._pending_tasks: Set[asyncio.Future] = set()
        self._initialized = False
        register_shutdown_handler(self.cleanup)
    
    async def initialize(self):
        """Initialize the retry manager."""
        if not self._initialized:
            try:
                # Any retry manager-specific initialization can go here
                self._initialized = True
                log("Database retry manager initialized", level="info")
            except Exception as e:
                log(f"Error initializing database retry manager: {e}", level="error")
                raise
    
    async def execute_with_retry(
        self,
        operation_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute an operation with retry logic."""
        if not self._initialized:
            await self.initialize()
            
        operation_name = getattr(operation_func, "__name__", "database_operation")
        attempt = 0
        last_error = None
        
        # Start timer for performance tracking
        start_time = time.time()
        
        with ErrorBoundary(error_types=[DatabaseError, Neo4jError, PostgresError, Exception],
                           error_message=f"Error in retry operation: {operation_name}",
                           reraise=True) as outer_error_boundary:
            while attempt <= self.config.max_retries:
                try:
                    # Execute the operation using submit_async_task
                    future = submit_async_task(operation_func(*args, **kwargs))
                    self._pending_tasks.add(future)
                    try:
                        result = await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
                    
                    # If successful and not the first attempt, log success after retry
                    if attempt > 0:
                        total_time = time.time() - start_time
                        log(
                            f"Operation '{operation_name}' succeeded after {attempt} retries "
                            f"(total time: {total_time:.2f}s)",
                            level="info"
                        )
                    
                    return result
                    
                except Exception as e:
                    # Classify the error
                    if not isinstance(e, (RetryableError, NonRetryableError)):
                        classified_error = classify_error(e)
                    else:
                        classified_error = e
                    
                    # If non-retryable, raise immediately
                    if isinstance(classified_error, NonRetryableError):
                        error_msg = f"Non-retryable error in '{operation_name}': {str(e)}"
                        log(error_msg, level="error")
                        # Wrap the NonRetryableError in a DatabaseError for backward compatibility
                        db_error = DatabaseError(error_msg)
                        db_error.__cause__ = e
                        raise db_error
                    
                    # Handle retryable error
                    attempt += 1
                    last_error = e
                    
                    # If we've exceeded max retries, break out and raise
                    if attempt > self.config.max_retries:
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = self.config.calculate_delay(attempt - 1)
                    
                    log(
                        f"Retryable error in '{operation_name}' (attempt {attempt}/{self.config.max_retries}): "
                        f"{str(e)}. Retrying in {delay:.2f}s",
                        level="warn"
                    )
                    
                    # Wait before retrying using submit_async_task
                    future = submit_async_task(asyncio.sleep(delay))
                    self._pending_tasks.add(future)
                    try:
                        await asyncio.wrap_future(future)
                    finally:
                        self._pending_tasks.remove(future)
            
            # If we get here, all retries failed
            total_time = time.time() - start_time
            error_msg = (
                f"Operation '{operation_name}' failed after {self.config.max_retries} retries "
                f"(total time: {total_time:.2f}s). Last error: {str(last_error)}"
            )
            log(error_msg, level="error")
            raise DatabaseError(error_msg)
    
    async def cleanup(self):
        """Clean up all resources."""
        try:
            # Cancel and clean up any pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*[asyncio.wrap_future(f) for f in self._pending_tasks], return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("Database retry manager cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up database retry manager: {e}", level="error")
    
    def retry(
        self,
        max_retries: Optional[int] = None,
        base_delay: Optional[float] = None,
        max_delay: Optional[float] = None
    ):
        """Decorator for retrying operations with custom retry parameters."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Create a custom retry config if any parameters are overridden
                if any(param is not None for param in [max_retries, base_delay, max_delay]):
                    custom_config = RetryConfig(
                        max_retries=max_retries or self.config.max_retries,
                        base_delay=base_delay or self.config.base_delay,
                        max_delay=max_delay or self.config.max_delay,
                        jitter_factor=self.config.jitter_factor
                    )
                    temp_manager = DatabaseRetryManager(custom_config)
                    return await temp_manager.execute_with_retry(func, *args, **kwargs)
                else:
                    return await self.execute_with_retry(func, *args, **kwargs)
            return wrapper
        return decorator

# Default retry manager instance
default_retry_manager = DatabaseRetryManager()

# Register cleanup handler
async def cleanup_retry():
    """Cleanup retry utilities resources."""
    try:
        await default_retry_manager.cleanup()
        log("Retry utilities cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up retry utilities: {e}", level="error")

register_shutdown_handler(cleanup_retry)

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