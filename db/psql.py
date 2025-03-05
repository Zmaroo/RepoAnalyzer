import asyncpg
import asyncio
import logging
from psycopg2.extras import RealDictCursor, Json
from psycopg2 import pool
from config import PostgresConfig
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    DatabaseError,
    AsyncErrorBoundary,
    ErrorBoundary,
    PostgresError,
    ErrorSeverity
)
from db.retry_utils import DatabaseRetryManager, RetryConfig

import os

# Define your PostgreSQL configuration using environment variables or hardcoded values.
DATABASE_CONFIG = {
    "user": PostgresConfig.user,
    "password": PostgresConfig.password,
    "database": PostgresConfig.database,
    "host": PostgresConfig.host,
    "port": PostgresConfig.port,
}

_pool = None
# Initialize retry manager with default configuration
_retry_manager = DatabaseRetryManager()

class ConnectionError(DatabaseError):
    """Database connection specific errors."""
    pass

@handle_async_errors(error_types=(ConnectionError, PostgresError))
async def init_db_pool() -> None:
    """[6.1.1] Initialize the database connection pool."""
    global _pool
    try:
        async with AsyncErrorBoundary("db pool initialization", error_types=ConnectionError, severity=ErrorSeverity.CRITICAL):
            _pool = await asyncpg.create_pool(
                user=PostgresConfig.user,
                password=PostgresConfig.password,
                database=PostgresConfig.database,
                host=PostgresConfig.host,
                port=PostgresConfig.port,
                min_size=5,
                max_size=20
            )
            
            # Test connection
            async with _pool.acquire() as conn:
                await conn.execute('SELECT 1')
                
            log("Database pool initialized", level="info", context={
                "host": PostgresConfig.host,
                "database": PostgresConfig.database,
                "pool_size": _pool.get_size()
            })
            
    except Exception as e:
        log("Failed to initialize database pool", level="error", context={"error": str(e)})
        raise ConnectionError(f"Failed to initialize database pool: {str(e)}")

@handle_async_errors(error_types=DatabaseError)
async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None

@handle_async_errors(error_types=DatabaseError, default_return=[])
async def query(sql: str, params: tuple = None) -> list:
    """Execute a query and return results."""
    if not _pool:
        raise DatabaseError("Database pool not initialized")
    
    async def _execute_query():
        async with _pool.acquire() as conn:
            async with conn.transaction():
                if params:
                    results = await conn.fetch(sql, *params)
                else:
                    results = await conn.fetch(sql)
                return [dict(row) for row in results]
    
    # Use retry manager to execute the query with retry logic
    return await _retry_manager.execute_with_retry(_execute_query)

@handle_async_errors(error_types=DatabaseError)
async def execute(sql: str, params: tuple = None) -> None:
    """Execute a SQL command."""
    if not _pool:
        raise DatabaseError("Database pool not initialized")
    
    async def _execute_command():
        async with _pool.acquire() as conn:
            async with conn.transaction():
                if params:
                    await conn.execute(sql, *params)
                else:
                    await conn.execute(sql)
    
    # Use retry manager to execute the command with retry logic
    await _retry_manager.execute_with_retry(_execute_command)

@handle_async_errors(error_types=DatabaseError)
async def execute_many(sql: str, params_list: list) -> None:
    """Execute a SQL command with multiple parameter sets."""
    if not _pool:
        raise DatabaseError("Database pool not initialized")
    
    async def _execute_many_command():
        async with _pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(sql, params_list)
    
    # Use retry manager to execute the command with retry logic
    await _retry_manager.execute_with_retry(_execute_many_command)

@handle_async_errors(error_types=DatabaseError)
async def get_connection():
    """Get a database connection from the pool."""
    if not _pool:
        raise DatabaseError("Database pool not initialized")
    return await _pool.acquire()

@handle_async_errors(error_types=DatabaseError)
async def release_connection(conn):
    """Release a database connection back to the pool."""
    await _pool.release(conn)

