"""[6.1] PostgreSQL database operations.

This module provides high-level database operations using the centralized connection manager.
All connection management is handled by the connection_manager.
"""

import asyncio
from typing import Optional, List, Dict, Any, Tuple
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    DatabaseError,
    AsyncErrorBoundary,
    PostgresError,
    ErrorSeverity
)
from db.retry_utils import DatabaseRetryManager, RetryConfig
from utils.async_runner import submit_async_task, get_loop
from db.connection import connection_manager
from utils.shutdown import register_shutdown_handler

# Initialize retry manager for database operations
_retry_manager = DatabaseRetryManager(RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0))

@handle_async_errors(error_types=DatabaseError, default_return=[])
async def query(sql: str, params: tuple = None) -> List[Dict[str, Any]]:
    """Execute a query and return results."""
    async def _execute_query():
        conn = await connection_manager.get_postgres_connection()
        try:
            async with conn.transaction():
                if params:
                    results = await conn.fetch(sql, *params)
                else:
                    results = await conn.fetch(sql)
                return [dict(row) for row in results]
        except Exception as e:
            await connection_manager.release_postgres_connection(conn)
            raise
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    return await _retry_manager.execute_with_retry(_execute_query)

@handle_async_errors(error_types=DatabaseError)
async def execute(sql: str, params: tuple = None) -> None:
    """Execute a SQL command."""
    async def _execute_command():
        conn = await connection_manager.get_postgres_connection()
        try:
            async with conn.transaction():
                if params:
                    await conn.execute(sql, *params)
                else:
                    await conn.execute(sql)
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    await _retry_manager.execute_with_retry(_execute_command)

@handle_async_errors(error_types=DatabaseError)
async def execute_many(sql: str, params_list: list) -> None:
    """Execute a SQL command with multiple parameter sets."""
    async def _execute_many_command():
        conn = await connection_manager.get_postgres_connection()
        try:
            async with conn.transaction():
                await conn.executemany(sql, params_list)
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    await _retry_manager.execute_with_retry(_execute_many_command)

async def execute_batch(
    sql: str,
    params_list: List[Tuple],
    batch_size: int = 1000
) -> None:
    """Execute a batch of SQL commands efficiently."""
    async def _execute_batch():
        conn = await connection_manager.get_postgres_connection()
        try:
            async with conn.transaction():
                for i in range(0, len(params_list), batch_size):
                    batch = params_list[i:i + batch_size]
                    await conn.executemany(sql, batch)
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    await _retry_manager.execute_with_retry(_execute_batch)

async def execute_parallel_queries(
    queries: List[Tuple[str, Optional[Tuple]]]
) -> List[List[Dict[str, Any]]]:
    """Execute multiple queries in parallel."""
    async def _execute_single_query(sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        conn = await connection_manager.get_postgres_connection()
        try:
            async with conn.transaction():
                if params:
                    results = await conn.fetch(sql, *params)
                else:
                    results = await conn.fetch(sql)
                return [dict(row) for row in results]
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    # Create tasks for all queries
    tasks = [_execute_single_query(sql, params) for sql, params in queries]
    
    # Wait for all queries to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Check for errors
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            log(f"Error executing query {i}: {result}", level="error")
            raise DatabaseError(f"Failed to execute parallel query {i}: {str(result)}")
    
    return results

# Register cleanup handler
async def cleanup_psql():
    """Cleanup PostgreSQL resources."""
    try:
        # Any PostgreSQL-specific cleanup can go here
        await _retry_manager.cleanup()
        log("PostgreSQL resources cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up PostgreSQL resources: {e}", level="error")

register_shutdown_handler(cleanup_psql)

