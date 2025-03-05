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
from typing import Any, Callable, Dict, List, Optional, Type, Union, Set, Awaitable
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
    """Configuration for retry behavior with AI operation support."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        ai_operation_timeout: float = 300.0,  # 5 minutes for AI operations
        ai_retry_multiplier: float = 2.0  # Longer delays for AI operations
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.ai_operation_timeout = ai_operation_timeout
        self.ai_retry_multiplier = ai_retry_multiplier

class RetryManager:
    """Manages retries for database operations with AI support."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self._ai_operation_stats = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_operations": 0
        }
    
    async def execute_with_retry(
        self,
        operation: Callable[..., Awaitable[T]],
        *args,
        is_ai_operation: bool = False,
        **kwargs
    ) -> T:
        """Execute an operation with retry logic, with special handling for AI operations."""
        last_exception = None
        base_delay = self.config.base_delay
        
        # Adjust delay for AI operations
        if is_ai_operation:
            base_delay *= self.config.ai_retry_multiplier
        
        for attempt in range(self.config.max_retries):
            try:
                # Set timeout for AI operations
                if is_ai_operation:
                    async with asyncio.timeout(self.config.ai_operation_timeout):
                        result = await operation(*args, **kwargs)
                else:
                    result = await operation(*args, **kwargs)
                
                if attempt > 0:
                    self._ai_operation_stats["successful_retries"] += 1
                return result
            
            except asyncio.TimeoutError as e:
                last_exception = e
                if is_ai_operation:
                    log(f"AI operation timeout on attempt {attempt + 1}", level="warn")
                else:
                    log(f"Operation timeout on attempt {attempt + 1}", level="warn")
            
            except Exception as e:
                last_exception = e
                if is_ai_operation:
                    log(f"AI operation failed on attempt {attempt + 1}: {str(e)}", level="warn")
                else:
                    log(f"Operation failed on attempt {attempt + 1}: {str(e)}", level="warn")
            
            # Update stats
            self._ai_operation_stats["total_retries"] += 1
            
            if attempt < self.config.max_retries - 1:
                delay = min(base_delay * (2 ** attempt), self.config.max_delay)
                await asyncio.sleep(delay)
        
        # Update failed operations count
        self._ai_operation_stats["failed_operations"] += 1
        
        if isinstance(last_exception, asyncio.TimeoutError):
            raise TimeoutError(f"Operation timed out after {self.config.max_retries} attempts")
        raise last_exception if last_exception else RuntimeError("Operation failed after max retries")
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about AI operation retries."""
        return self._ai_operation_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset AI operation statistics."""
        self._ai_operation_stats = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_operations": 0
        }

# Create global retry manager instance with AI support
retry_manager = RetryManager(RetryConfig())

# Export with proper async handling
async def get_retry_manager() -> RetryManager:
    """Get the retry manager instance.
    
    Returns:
        RetryManager: The singleton retry manager instance
    """
    return retry_manager

# Default retry manager instance
default_retry_manager = None

async def get_retry_manager_old() -> 'DatabaseRetryManager':
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