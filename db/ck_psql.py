"""PostgreSQL database check utility.

This module provides utilities for checking PostgreSQL database tables and their contents.
"""

import asyncio
from pprint import pprint
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    PostgresError,
    ErrorSeverity
)
from utils.logger import log
from db.psql import query
from db.connection import connection_manager
from utils.async_runner import get_loop
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import global_health_monitor, ComponentStatus, monitor_database
from utils.request_cache import cached_in_request
from typing import Dict, Any
import time

# Initialize cache
_cache = UnifiedCache("db_check")
_metrics = {
    "total_checks": 0,
    "successful_checks": 0,
    "failed_checks": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "check_times": []
}

async def _check_health() -> Dict[str, Any]:
    """Health check for database check utility."""
    # Calculate average check time
    avg_check_time = sum(_metrics["check_times"]) / len(_metrics["check_times"]) if _metrics["check_times"] else 0
    
    # Calculate health status
    status = ComponentStatus.HEALTHY
    details = {
        "metrics": {
            "total_checks": _metrics["total_checks"],
            "success_rate": _metrics["successful_checks"] / _metrics["total_checks"] if _metrics["total_checks"] > 0 else 0,
            "cache_hit_rate": _metrics["cache_hits"] / (_metrics["cache_hits"] + _metrics["cache_misses"]) if (_metrics["cache_hits"] + _metrics["cache_misses"]) > 0 else 0,
            "avg_check_time": avg_check_time
        }
    }
    
    # Check for degraded conditions
    if details["metrics"]["success_rate"] < 0.8:
        status = ComponentStatus.DEGRADED
        details["reason"] = "Low check success rate"
    elif avg_check_time > 1.0:
        status = ComponentStatus.DEGRADED
        details["reason"] = "High check times"
    
    return {
        "status": status,
        "details": details
    }

@handle_async_errors(error_types=[PostgresError])
async def check_all_postgres_tables():
    """Check and display contents of all PostgreSQL tables."""
    print("\n==========================================")
    print("     PostgreSQL Database Check")
    print("==========================================\n")
    
    # Dictionary defining table names and their corresponding queries
    tables = {
        "Repositories": "SELECT * FROM repositories ORDER BY id;",
        "Code Snippets": "SELECT * FROM code_snippets ORDER BY id;",
        "Repository Documents": "SELECT * FROM repo_docs ORDER BY id;",
        "Repo Doc Relations": "SELECT * FROM repo_doc_relations ORDER BY repo_id, doc_id;",
        "Document Versions": "SELECT * FROM doc_versions ORDER BY id;",
        "Document Clusters": "SELECT * FROM doc_clusters ORDER BY id;"
    }
    
    tasks = []
    try:
        # Initialize PostgreSQL connection
        await connection_manager.initialize_postgres()
        
        start_time = time.time()
        _metrics["total_checks"] += 1
        
        for table_name, sql in tables.items():
            with AsyncErrorBoundary(
                operation_name=f"Error querying {table_name}",
                error_types=[PostgresError, Exception],
                severity=ErrorSeverity.ERROR
            ) as error_boundary:
                # Check cache first
                cache_key = f"table_check:{table_name}"
                cached_result = await _cache.get_async(cache_key)
                if cached_result:
                    _metrics["cache_hits"] += 1
                    records = cached_result
                else:
                    _metrics["cache_misses"] += 1
                    with monitor_database("postgres", f"check_{table_name}"):
                        task = asyncio.create_task(query(sql))
                        tasks.append((table_name, task))
        
        # Wait for all queries to complete
        for table_name, task in tasks:
            try:
                records = await task
                print(f"{table_name}:")
                print("-" * len(table_name))
                print(f"Total entries: {len(records)}")
                for record in records:
                    pprint(dict(record))
                print("\n")
                
                # Cache successful results
                await _cache.set_async(f"table_check:{table_name}", records)
                _metrics["successful_checks"] += 1
            except Exception as e:
                log(f"Error querying {table_name}: {e}", level="error")
                print(f"Error querying {table_name}: {e}")
                _metrics["failed_checks"] += 1
        
        # Record check time
        check_time = time.time() - start_time
        _metrics["check_times"].append(check_time)
        
        # Update health status
        await global_health_monitor.update_component_status(
            "db_check",
            ComponentStatus.HEALTHY if _metrics["successful_checks"] > 0 else ComponentStatus.DEGRADED,
            response_time=check_time * 1000,  # Convert to ms
            error=_metrics["failed_checks"] > 0
        )
    finally:
        # Close all connections
        await connection_manager.cleanup()

# Register with health monitor
global_health_monitor.register_component("db_check", health_check=_check_health)

# Initialize module
async def initialize():
    """Initialize database check module."""
    # Register cache with coordinator
    await cache_coordinator.register_cache("db_check", _cache)
    log("Database check module initialized", level="info")

# Register cleanup handler
async def cleanup_check():
    """Cleanup check utility resources."""
    try:
        await connection_manager.cleanup()
        await _cache.clear_async()
        await cache_coordinator.unregister_cache("db_check")
        log("Check utility resources cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up check utility resources: {e}", level="error")

register_shutdown_handler(cleanup_check)

if __name__ == "__main__":
    loop = get_loop()
    loop.run_until_complete(initialize())
    loop.run_until_complete(check_all_postgres_tables())

@cached_in_request
async def query_tables(self, tables: Dict[str, str]) -> Dict[str, Any]:
    """Query multiple tables with error handling."""
    results = {}
    
    for table_name, sql in tables.items():
        async with AsyncErrorBoundary(
            operation_name=f"Error querying {table_name}",
            error_types=[PostgresError, Exception],
            severity=ErrorSeverity.ERROR
        ) as error_boundary:
            try:
                conn = await self.get_connection()
                with monitor_database("postgres", f"query_{table_name}"):
                    result = await conn.fetch(sql)
                results[table_name] = result
            except Exception as e:
                log(f"Error querying {table_name}: {e}", level="error")
                results[table_name] = None
            finally:
                await self.release_connection(conn)
    
    return results