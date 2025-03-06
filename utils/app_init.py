"""Application initialization and lifecycle management."""

import asyncio
import atexit
import os
import sys
from typing import Callable, List, Optional

from utils.logger import log
from utils.async_runner import cleanup_tasks, submit_async_task, get_loop
from utils.cache import cache_coordinator
from utils.cache_analytics import start_cache_analytics
from utils.shutdown import execute_shutdown_handlers
from db.connection import connection_manager

async def _initialize_components():
    """Initialize all application components asynchronously."""
    try:
        # Initialize logging first
        from utils.logger import logger
        logger._initialize_logger()
        log("Logging system initialized", level="info")
        
        # Initialize error handling
        from utils.error_handling import ErrorAudit
        log("Initializing error handling...")
        # Directly await the analyze_codebase call
        await ErrorAudit.analyze_codebase(os.getcwd())
        log("Error handling initialized")
        
        # Initialize databases
        from db.psql import init_db_pool
        await init_db_pool()
        log("PostgreSQL pool initialized", level="info")
        
        # Initialize Neo4j schema
        from db.neo4j_ops import initialize_schema
        await initialize_schema()
        log("Neo4j schema initialized", level="info")
        
        # Initialize caching system in proper order
        from utils.cache import initialize_caches, cleanup_caches, cache_coordinator
        from utils.cache_analytics import initialize_cache_analytics, cache_analytics
        
        # Initialize base caching first
        initialize_caches()
        log("Base cache system initialized", level="info")
        
        # Initialize cache analytics with the coordinator
        await initialize_cache_analytics(cache_coordinator)
        log("Cache analytics initialized", level="info")
        
        # Initialize embedders
        from embedding.embedding_models import init_embedders
        await init_embedders()
        log("Embedders initialized", level="info")
        
        # Initialize health monitoring
        from utils.health_monitor import global_health_monitor
        global_health_monitor.start_monitoring()
        log("Health monitoring started", level="info")
        
        # Register cleanup handlers in reverse initialization order
        from db.psql import close_db_pool
        
        # Health monitoring cleanup
        from utils.shutdown import register_shutdown_handler
        register_shutdown_handler(global_health_monitor.cleanup)
        
        # Cache system cleanup (should be after components that might use cache)
        register_shutdown_handler(cache_analytics.cleanup)
        register_shutdown_handler(cleanup_caches)
        
        # Database cleanup (should be last as other cleanups might need DB)
        register_shutdown_handler(close_db_pool)
        
        # Create an async cleanup function for Neo4j
        async def async_neo4j_close():
            try:
                await connection_manager.cleanup()
                log("Neo4j connection closed successfully", level="info")
            except Exception as e:
                log(f"Error closing Neo4j connection: {e}", level="error")
        
        # Register the async cleanup function by wrapping it in a sync function
        def sync_neo4j_close():
            loop = get_loop()
            future = submit_async_task(async_neo4j_close())
            loop.run_until_complete(asyncio.wrap_future(future))
        
        # Register the sync wrapper function
        register_shutdown_handler(sync_neo4j_close)
        
        # Async tasks cleanup should be very last
        register_shutdown_handler(cleanup_tasks)
        
        log("Application components initialized successfully", level="info")
    except Exception as e:
        log(f"Error initializing application components: {e}", level="error")
        raise

async def initialize_application():
    """Initialize the application and all its components."""
    try:
        log("Initializing application...", level="info")
        
        # Register the cleanup handler
        atexit.register(lambda: asyncio.run(execute_shutdown_handlers()))
        
        # Initialize components
        await _initialize_components()
        
        log("Application initialized successfully", level="info")
        return True
    except Exception as e:
        log(f"Application initialization failed: {e}", level="error")
        return False

if __name__ == "__main__":
    # Use get_loop from async_runner instead of creating a new one
    loop = get_loop()
    success = loop.run_until_complete(initialize_application())
    if not success:
        sys.exit(1) 