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
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_database
from utils.request_cache import cached_in_request
import time

# Initialize retry manager with AI-specific configuration
_retry_manager = RetryManager(RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    ai_operation_timeout=300.0,  # 5 minutes for AI operations
    ai_retry_multiplier=2.0  # Longer delays for AI operations
))

# Initialize cache
_query_cache = UnifiedCache("psql_queries")

# Initialize metrics
_metrics = {
    "total_queries": 0,
    "successful_queries": 0,
    "failed_queries": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "query_times": []
}

async def _check_health() -> Dict[str, Any]:
    """Health check for PostgreSQL operations."""
    # Calculate average query time
    avg_query_time = sum(_metrics["query_times"]) / len(_metrics["query_times"]) if _metrics["query_times"] else 0
    
    # Calculate health status
    status = ComponentStatus.HEALTHY
    details = {
        "metrics": {
            "total_queries": _metrics["total_queries"],
            "success_rate": _metrics["successful_queries"] / _metrics["total_queries"] if _metrics["total_queries"] > 0 else 0,
            "cache_hit_rate": _metrics["cache_hits"] / (_metrics["cache_hits"] + _metrics["cache_misses"]) if (_metrics["cache_hits"] + _metrics["cache_misses"]) > 0 else 0,
            "avg_query_time": avg_query_time
        }
    }
    
    # Check for degraded conditions
    if details["metrics"]["success_rate"] < 0.8:
        status = ComponentStatus.DEGRADED
        details["reason"] = "Low query success rate"
    elif avg_query_time > 1.0:
        status = ComponentStatus.DEGRADED
        details["reason"] = "High query times"
    
    return {
        "status": status,
        "details": details
    }

@handle_async_errors(error_types=DatabaseError, default_return=[])
@cached_in_request
async def query(
    sql: str,
    params: tuple = None,
    is_ai_operation: bool = False
) -> List[Dict[str, Any]]:
    """Execute a query and return results."""
    start_time = time.time()
    _metrics["total_queries"] += 1
    
    # Check cache first
    cache_key = f"query:{sql}:{str(params)}"
    cached_result = await _query_cache.get_async(cache_key)
    if cached_result:
        _metrics["cache_hits"] += 1
        return cached_result
    
    _metrics["cache_misses"] += 1
    
    async def _execute_query():
        conn = await connection_manager.get_connection()
        try:
            async with conn.transaction():
                if is_ai_operation:
                    # Set longer timeout for AI operations
                    await conn.execute("SET LOCAL statement_timeout = '300s'")
                
                with monitor_database("postgres", "query"):
                    if params:
                        results = await conn.fetch(sql, *params)
                    else:
                        results = await conn.fetch(sql)
                    return [dict(row) for row in results]
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    try:
        results = await _retry_manager.execute_with_retry(
            _execute_query,
            is_ai_operation=is_ai_operation
        )
        
        # Cache successful results
        await _query_cache.set_async(cache_key, results)
        
        # Update metrics
        _metrics["successful_queries"] += 1
        query_time = time.time() - start_time
        _metrics["query_times"].append(query_time)
        
        # Update health status
        await global_health_monitor.update_component_status(
            "psql_operations",
            ComponentStatus.HEALTHY,
            response_time=query_time * 1000,  # Convert to ms
            error=False
        )
        
        return results
    except Exception as e:
        _metrics["failed_queries"] += 1
        # Update health status
        await global_health_monitor.update_component_status(
            "psql_operations",
            ComponentStatus.DEGRADED,
            error=True,
            details={"error": str(e)}
        )
        raise

@handle_async_errors(error_types=DatabaseError)
async def execute(
    sql: str,
    params: tuple = None,
    is_ai_operation: bool = False
) -> None:
    """Execute a SQL command."""
    start_time = time.time()
    _metrics["total_queries"] += 1
    
    async def _execute_command():
        conn = await connection_manager.get_connection()
        try:
            async with conn.transaction():
                if is_ai_operation:
                    await conn.execute("SET LOCAL statement_timeout = '300s'")
                
                with monitor_database("postgres", "execute"):
                    if params:
                        await conn.execute(sql, *params)
                    else:
                        await conn.execute(sql)
        finally:
            await connection_manager.release_postgres_connection(conn)
    
    try:
        await _retry_manager.execute_with_retry(
            _execute_command,
            is_ai_operation=is_ai_operation
        )
        
        # Update metrics
        _metrics["successful_queries"] += 1
        query_time = time.time() - start_time
        _metrics["query_times"].append(query_time)
        
        # Update health status
        await global_health_monitor.update_component_status(
            "psql_operations",
            ComponentStatus.HEALTHY,
            response_time=query_time * 1000,
            error=False
        )
    except Exception as e:
        _metrics["failed_queries"] += 1
        # Update health status
        await global_health_monitor.update_component_status(
            "psql_operations",
            ComponentStatus.DEGRADED,
            error=True,
            details={"error": str(e)}
        )
        raise

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

# Initialize module
async def initialize():
    """Initialize PostgreSQL operations module."""
    # Register cache with coordinator
    await cache_coordinator.register_cache("psql_queries", _query_cache)
    
    # Register with health monitor
    global_health_monitor.register_component("psql_operations", health_check=_check_health)
    
    log("PostgreSQL operations module initialized", level="info")

# Register cleanup handler
async def cleanup_psql():
    """Cleanup PostgreSQL resources."""
    try:
        await _retry_manager.cleanup()
        await _query_cache.clear_async()
        await cache_coordinator.unregister_cache("psql_queries")
        log("PostgreSQL resources cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up PostgreSQL resources: {e}", level="error")

register_shutdown_handler(cleanup_psql)

# Export the module's functions
__all__ = [
    'query',
    'execute',
    'execute_many',
    'execute_batch',
    'execute_parallel_queries',
    'execute_vector_similarity_search',
    'execute_pattern_metrics_update',
    'initialize',
    'cleanup_psql'
]

