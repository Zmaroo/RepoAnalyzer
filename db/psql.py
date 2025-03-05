"""[6.1] PostgreSQL database operations with AI support.

This module provides high-level database operations using the centralized connection manager,
with special handling for AI-enhanced operations.
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
from db.retry_utils import RetryManager, RetryConfig
from utils.async_runner import submit_async_task, get_loop
from db.connection import connection_manager
from utils.shutdown import register_shutdown_handler

# Initialize retry manager with AI-specific configuration
_retry_manager = RetryManager(RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    ai_operation_timeout=300.0,  # 5 minutes for AI operations
    ai_retry_multiplier=2.0  # Longer delays for AI operations
))

@handle_async_errors(error_types=DatabaseError, default_return=[])
async def query(
    sql: str,
    params: tuple = None,
    is_ai_operation: bool = False
) -> List[Dict[str, Any]]:
    """Execute a query and return results."""
    async def _execute_query():
        conn = await connection_manager.get_connection()
        try:
            async with conn.transaction():
                if is_ai_operation:
                    # Set longer timeout for AI operations
                    await conn.execute("SET LOCAL statement_timeout = '300s'")
                
                if params:
                    results = await conn.fetch(sql, *params)
                else:
                    results = await conn.fetch(sql)
                return [dict(row) for row in results]
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    return await _retry_manager.execute_with_retry(
        _execute_query,
        is_ai_operation=is_ai_operation
    )

@handle_async_errors(error_types=DatabaseError)
async def execute(
    sql: str,
    params: tuple = None,
    is_ai_operation: bool = False
) -> None:
    """Execute a SQL command."""
    async def _execute_command():
        conn = await connection_manager.get_connection()
        try:
            async with conn.transaction():
                if is_ai_operation:
                    await conn.execute("SET LOCAL statement_timeout = '300s'")
                
                if params:
                    await conn.execute(sql, *params)
                else:
                    await conn.execute(sql)
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    await _retry_manager.execute_with_retry(
        _execute_command,
        is_ai_operation=is_ai_operation
    )

@handle_async_errors(error_types=DatabaseError)
async def execute_many(
    sql: str,
    params_list: list,
    is_ai_operation: bool = False
) -> None:
    """Execute a SQL command with multiple parameter sets."""
    async def _execute_many_command():
        conn = await connection_manager.get_connection()
        try:
            async with conn.transaction():
                if is_ai_operation:
                    await conn.execute("SET LOCAL statement_timeout = '300s'")
                await conn.executemany(sql, params_list)
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    await _retry_manager.execute_with_retry(
        _execute_many_command,
        is_ai_operation=is_ai_operation
    )

async def execute_batch(
    sql: str,
    params_list: List[Tuple],
    batch_size: int = 1000,
    is_ai_operation: bool = False
) -> None:
    """Execute a batch of SQL commands efficiently."""
    async def _execute_batch():
        conn = await connection_manager.get_connection()
        try:
            async with conn.transaction():
                if is_ai_operation:
                    await conn.execute("SET LOCAL statement_timeout = '300s'")
                for i in range(0, len(params_list), batch_size):
                    batch = params_list[i:i + batch_size]
                    await conn.executemany(sql, batch)
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    await _retry_manager.execute_with_retry(
        _execute_batch,
        is_ai_operation=is_ai_operation
    )

async def execute_parallel_queries(
    queries: List[Tuple[str, Optional[Tuple]]],
    is_ai_operation: bool = False
) -> List[List[Dict[str, Any]]]:
    """Execute multiple queries in parallel."""
    async def _execute_single_query(sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        conn = await connection_manager.get_connection()
        try:
            async with conn.transaction():
                if is_ai_operation:
                    await conn.execute("SET LOCAL statement_timeout = '300s'")
                if params:
                    results = await conn.fetch(sql, *params)
                else:
                    results = await conn.fetch(sql)
                return [dict(row) for row in results]
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    # Create tasks for all queries
    tasks = [
        _retry_manager.execute_with_retry(
            lambda: _execute_single_query(sql, params),
            is_ai_operation=is_ai_operation
        )
        for sql, params in queries
    ]
    
    # Wait for all queries to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Check for errors
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            log(f"Error executing query {i}: {result}", level="error")
            raise DatabaseError(f"Failed to execute parallel query {i}: {str(result)}")
    
    return results

async def execute_vector_similarity_search(
    table: str,
    embedding: List[float],
    limit: int = 10,
    min_similarity: float = 0.7
) -> List[Dict[str, Any]]:
    """Execute vector similarity search optimized for AI operations."""
    sql = f"""
    SELECT *,
           1 - (embedding <=> $1::vector) as similarity
    FROM {table}
    WHERE 1 - (embedding <=> $1::vector) >= $2
    ORDER BY similarity DESC
    LIMIT $3
    """
    
    return await query(
        sql,
        (embedding, min_similarity, limit),
        is_ai_operation=True
    )

async def execute_pattern_metrics_update(
    pattern_id: int,
    metrics: Dict[str, Any]
) -> None:
    """Update pattern metrics with AI insights."""
    sql = """
    INSERT INTO pattern_metrics (
        pattern_id,
        complexity_score,
        maintainability_score,
        reusability_score,
        ai_quality_score,
        ai_impact_score,
        ai_trend_analysis,
        updated_at
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP)
    ON CONFLICT (pattern_id)
    DO UPDATE SET
        complexity_score = EXCLUDED.complexity_score,
        maintainability_score = EXCLUDED.maintainability_score,
        reusability_score = EXCLUDED.reusability_score,
        ai_quality_score = EXCLUDED.ai_quality_score,
        ai_impact_score = EXCLUDED.ai_impact_score,
        ai_trend_analysis = EXCLUDED.ai_trend_analysis,
        updated_at = CURRENT_TIMESTAMP
    """
    
    await execute(
        sql,
        (
            pattern_id,
            metrics.get("complexity_score"),
            metrics.get("maintainability_score"),
            metrics.get("reusability_score"),
            metrics.get("ai_quality_score"),
            metrics.get("ai_impact_score"),
            metrics.get("ai_trend_analysis")
        ),
        is_ai_operation=True
    )

# Register cleanup handler
async def cleanup_psql():
    """Cleanup PostgreSQL resources."""
    try:
        await _retry_manager.cleanup()
        log("PostgreSQL resources cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up PostgreSQL resources: {e}", level="error")

register_shutdown_handler(cleanup_psql)

