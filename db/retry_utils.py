"""
Retry utilities for database operations.

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
from typing import Any, Callable, Dict, List, Optional, Type, Union
from neo4j.exceptions import Neo4jError, ServiceUnavailable, ClientError
from psycopg.errors import OperationalError as PostgresError
from utils.logger import log
from utils.error_handling import DatabaseError, Neo4jError, TransactionError, handle_async_errors, ErrorBoundary, PostgresError, AsyncErrorBoundary


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


RETRYABLE_ERROR_PATTERNS = ['connection', 'timeout', 'deadlock', 'lock',
    'unavailable', 'temporary', 'overloaded', 'too busy', 'refused',
    'reset', 'broken pipe', 'closed connection', 'connection abort',
    'connectivity', 'socket', 'network', 'unreachable',
    'operation interrupted', 'concurrent', 'temporary failure']
NON_RETRYABLE_ERROR_PATTERNS = ['syntax error', 'constraint', 'invalid',
    'not found', 'already exists', 'schema', 'authentication',
    'authorization', 'permission', 'type error', 'value error',
    'index error', 'out of bounds', 'null', 'undefined']


@handle_errors(error_types=(Exception,))
def is_retryable_error(error: Exception) ->bool:
    """
    Determine if an error is retryable based on its error message.
    
    Args:
        error: The exception to check
        
    Returns:
        bool: True if the error is retryable, False otherwise
    """
    error_msg = str(error).lower()
    if isinstance(error, NonRetryableError):
        return False
    if isinstance(error, RetryableError):
        return True
    if any(pattern in error_msg for pattern in NON_RETRYABLE_ERROR_PATTERNS):
        return False
    if any(pattern in error_msg for pattern in RETRYABLE_ERROR_PATTERNS):
        return True
    return isinstance(error, (Neo4jError, TransactionError, ConnectionError,
        OSError))

@handle_errors(error_types=(Exception,))

def classify_error(error: Exception) ->Exception:
    """
    Classify an error as retryable or non-retryable.
    
    Args:
        error: The exception to classify
        
    Returns:
        Exception: Either RetryableNeo4jError or NonRetryableNeo4jError
    """
    if is_retryable_error(error):
        return RetryableNeo4jError(str(error))
    else:
        return NonRetryableNeo4jError(str(error))


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(self, max_retries: int=3, base_delay: float=1.0, max_delay:
        float=30.0, jitter_factor: float=0.1):
        """
        Initialize retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds
            jitter_factor: Factor to apply randomness to delay (0.0-1.0)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
@handle_errors(error_types=(Exception,))
        self.jitter_factor = jitter_factor

    def calculate_delay(self, attempt: int) ->float:
        """
        Calculate delay for a given attempt using exponential backoff with jitter.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            float: Delay in seconds
        """
        delay = self.base_delay * 2 ** attempt
        delay = min(delay, self.max_delay)
        jitter = random.uniform(-self.jitter_factor, self.jitter_factor)
        delay = delay * (1 + jitter)
        return delay


class DatabaseRetryManager:
    """
    Manager for database operations with comprehensive retry functionality.
    
    This class provides methods to execute database operations with 
    exponential backoff retry logic, proper error classification,
    and detailed logging.
    """

    def __init__(self, config: RetryConfig=None):
        """
        Initialize the database retry manager.
        
        Args:
            config: Retry configuration (optional)
        """
        self.config = config or RetryConfig()

    @handle_async_errors(error_types=(DatabaseError, Neo4jError,
        PostgresError, RetryableError, NonRetryableError))
    async def execute_with_retry(self, operation_func: Callable, *args, **
        kwargs) ->Any:
        """
        Execute an operation with retry logic.
        
        Args:
            operation_func: Function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Any: The result of the operation
            
        Raises:
            DatabaseError: If all retries fail or a non-retryable error occurs
        """
        operation_name = getattr(operation_func, '__name__',
            'database_operation')
        attempt = 0
        last_error = None
        start_time = time.time()
        with AsyncErrorBoundary(operation_name=
            f'Retry operation: {operation_name}', error_types=(
            DatabaseError, Neo4jError, PostgresError, Exception)
            ) as error_boundary:
            while attempt <= self.config.max_retries:
                try:
                    result = await operation_func(*args, **kwargs)
                    if attempt > 0:
                        total_time = time.time() - start_time
                        log(f"Operation '{operation_name}' succeeded after {attempt} retries (total time: {total_time:.2f}s)"
                            , level='info')
                    return result
                except Exception as e:
                    if not isinstance(e, (RetryableError, NonRetryableError)):
                        classified_error = classify_error(e)
                    else:
                        classified_error = e
                    if isinstance(classified_error, NonRetryableError):
                        error_msg = (
                            f"Non-retryable error in '{operation_name}': {str(e)}"
                            )
                        log(error_msg, level='error')
                        raise DatabaseError(error_msg) from e
                    attempt += 1
                    last_error = e
                    if attempt > self.config.max_retries:
                        break
                    delay = self.config.calculate_delay(attempt - 1)
                    log(f"Retryable error in '{operation_name}' (attempt {attempt}/{self.config.max_retries}): {str(e)}. Retrying in {delay:.2f}s"
                        , level='warn')
                    await asyncio.sleep(delay)
            total_time = time.time() - start_time
            error_msg = (
                f"All {self.config.max_retries} retries failed for '{operation_name}' (total time: {total_time:.2f}s): {str(last_error)}"
                )
            log(error_msg, level='error')
            raise DatabaseError(error_msg) from last_error
        if error_boundary.error:
            log(f'Unexpected error in retry mechanism: {error_boundary.error}',
                level='error')
@handle_errors(error_types=(Exception,))
            raise DatabaseError(
                f'Retry mechanism failed: {str(error_boundary.error)}')

    def retry(self, max_retries: Optional[int]=None, base_delay: Optional[
        float]=None, max_delay: Optional[float]=None):
        """
        Decorator to apply retry logic to a function.
        
        This decorator can be used to wrap async functions that need retry logic.
        
        Args:
            max_retries: Override default max retries
            base_delay: Override default base delay
            max_delay: Override default max delay
            
@handle_errors(error_types=(Exception,))
        Returns:
            Callable: Decorated function with retry logic
@handle_async_errors(error_types=(Exception,))
        """

        def decorator(func):

            @wraps(func)
            async def wrapper(*args, **kwargs):
                config = None
                if any(param is not None for param in [max_retries,
                    base_delay, max_delay]):
                    config = RetryConfig(max_retries=max_retries if 
                        max_retries is not None else self.config.
                        max_retries, base_delay=base_delay if base_delay is not
                        None else self.config.base_delay, max_delay=
                        max_delay if max_delay is not None else self.config
                        .max_delay, jitter_factor=self.config.jitter_factor)
                manager = self if config is None else DatabaseRetryManager(
                    config)
                return await manager.execute_with_retry(func, *args, **kwargs)
            return wrapper
        return decorator


default_retry_manager = DatabaseRetryManager()
@handle_errors(error_types=(Exception,))


def with_retry(max_retries: Optional[int]=None, base_delay: Optional[float]
    =None, max_delay: Optional[float]=None):
    """
    Decorator factory to apply retry logic to a function.
    
    This decorator can be used to wrap async functions that need retry logic.
    
    Args:
        max_retries: Override default max retries
        base_delay: Override default base delay
        max_delay: Override default max delay
        
    Returns:
        Callable: Decorated function with retry logic
    """
    return default_retry_manager.retry(max_retries=max_retries, base_delay=
        base_delay, max_delay=max_delay)
