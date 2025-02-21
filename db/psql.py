import asyncpg
import asyncio
import logging
from psycopg2.extras import RealDictCursor, Json
from psycopg2 import pool
from config import postgres_config
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    DatabaseError,
    AsyncErrorBoundary,
    ErrorBoundary
)
import os

# Create a thread-safe connection pool using the centralized configuration.
DB_POOL = pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host=postgres_config.host,
    user=postgres_config.user,
    password=postgres_config.password,
    database=postgres_config.database,
    port=postgres_config.port
)

# Define your PostgreSQL configuration using environment variables or hardcoded values.
DATABASE_CONFIG = {
    "user": postgres_config.user,
    "password": postgres_config.password,
    "database": postgres_config.database,
    "host": postgres_config.host,
    "port": postgres_config.port,
}

_pool = None

@handle_async_errors(error_types=DatabaseError)
async def init_db_pool() -> None:
    """Initialize the database connection pool."""
    global _pool
    try:
        _pool = await asyncpg.create_pool(
            user=postgres_config.user,
            password=postgres_config.password,
            database=postgres_config.database,
            host=postgres_config.host,
            port=postgres_config.port,
            min_size=5,
            max_size=20
        )
    except Exception as e:
        raise DatabaseError("Failed to initialize database pool", e)

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
        
    async with AsyncErrorBoundary("database query", error_types=DatabaseError):
        async with _pool.acquire() as conn:
            async with conn.transaction():
                if params:
                    results = await conn.fetch(sql, *params)
                else:
                    results = await conn.fetch(sql)
                return [dict(row) for row in results]

@handle_async_errors(error_types=DatabaseError)
async def execute(sql: str, params: tuple = None) -> None:
    """Execute a SQL command."""
    if not _pool:
        raise DatabaseError("Database pool not initialized")
        
    async with AsyncErrorBoundary("database execute", error_types=DatabaseError):
        async with _pool.acquire() as conn:
            async with conn.transaction():
                if params:
                    await conn.execute(sql, *params)
                else:
                    await conn.execute(sql)

@handle_async_errors(error_types=DatabaseError)
async def execute_many(sql: str, params_list: list) -> None:
    """Execute a SQL command with multiple parameter sets."""
    if not _pool:
        raise DatabaseError("Database pool not initialized")
        
    async with AsyncErrorBoundary("database execute many", error_types=DatabaseError):
        async with _pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(sql, params_list)

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

def query_sync(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            result = cur.fetchall() if cur.description else None
            conn.commit()
            return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_connection(conn)

