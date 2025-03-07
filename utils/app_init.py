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
from db.neo4j_ops import create_schema_indexes_and_constraints, get_neo4j_tools
from db.transaction import get_transaction_coordinator

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
        await ErrorAudit.analyze_codebase(os.getcwd())
        log("Error handling initialized")
        
        # Initialize connection manager first
        await connection_manager.initialize()
        log("Connection manager initialized", level="info")
        
        # Initialize transaction coordinator
        await get_transaction_coordinator()
        log("Transaction coordinator initialized", level="info")
        
        # Initialize PostgreSQL operations
        from db.psql import initialize as init_psql
        await init_psql()
        log("PostgreSQL operations initialized", level="info")
        
        # Initialize Neo4j tools
        neo4j_tools = await get_neo4j_tools()
        log("Neo4j tools initialized", level="info")
        
        # Then create Neo4j schema
        await create_schema_indexes_and_constraints()
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
        from utils.shutdown import register_shutdown_handler
        from db.psql import cleanup_psql
        from db.transaction import transaction_coordinator
        
        # Health monitoring cleanup
        register_shutdown_handler(global_health_monitor.cleanup)
        
        # Cache system cleanup (should be after components that might use cache)
        register_shutdown_handler(cache_analytics.cleanup)
        register_shutdown_handler(cleanup_caches)
        
        # Database cleanup (should be last as other cleanups might need DB)
        register_shutdown_handler(cleanup_psql)
        register_shutdown_handler(transaction_coordinator.cleanup)
        
        # Create an async cleanup function for Neo4j
        async def async_neo4j_close():
            try:
                await neo4j_tools.cleanup()  # Use the instance we created
                await connection_manager.cleanup()
                log("Neo4j resources closed successfully", level="info")
            except Exception as e:
                log(f"Error closing Neo4j resources: {e}", level="error")
        
        # Register the async cleanup function by wrapping it in a sync function
        def sync_neo4j_close():
            loop = get_loop()
            try:
                loop.run_until_complete(async_neo4j_close())
            except RuntimeError:
                # If the loop is already running, use submit_async_task
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
    try:
        success = loop.run_until_complete(initialize_application())
        if not success:
            sys.exit(1)
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            # If the loop is already running, use submit_async_task
            future = submit_async_task(initialize_application())
            success = loop.run_until_complete(asyncio.wrap_future(future))
            if not success:
                sys.exit(1) 