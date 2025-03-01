"""Application initialization and lifecycle management."""

import asyncio
import atexit
import os
import sys
import logging
import time
import threading
from typing import Callable, List, Optional, Dict, Any

from utils.logger import log
from utils.async_runner import cleanup_tasks
from utils.cache import cache_coordinator
from utils.cache_analytics import start_cache_analytics
from db.psql import init_db_pool, close_db_pool
from ai_tools.graph_capabilities import GraphAnalysis
from utils.error_handling import ErrorAudit
from utils.health_monitor import HealthMonitor

# List to keep track of registered shutdown handlers
_shutdown_handlers: List[Callable] = []
_cleanup_handlers = {}

def register_shutdown_handler(handler: Callable) -> None:
    """Register a function to be called during application shutdown."""
    _shutdown_handlers.append(handler)

def _cleanup_on_exit() -> None:
    """Handle all cleanup operations on application exit."""
    log("Application shutting down, performing cleanup...", level="info")
    
    # Execute all registered shutdown handlers
    for handler in _shutdown_handlers:
        try:
            handler()
        except Exception as e:
            log(f"Error in shutdown handler: {e}", level="error")
    
    # Clean up async tasks
    cleanup_tasks()
    
    log("Cleanup completed", level="info")

def db_cleanup() -> None:
    """Clean up database resources."""
    try:
        # Use get_event_loop().run_until_complete to run async function in sync context
        loop = asyncio.get_event_loop()
        loop.run_until_complete(close_db_pool())
        log("Database pool closed", level="info")
    except Exception as e:
        log(f"Error closing database pool: {e}", level="error")

def neo4j_projections_cleanup() -> None:
    """Clean up Neo4j projections."""
    try:
        from db.neo4j_ops import Neo4jProjections
        loop = asyncio.get_event_loop()
        projections = Neo4jProjections()
        
        # Properly await the coroutine
        if loop.is_running():
            # If we're in an async context, create a task
            asyncio.create_task(projections.close())
            log("Neo4j projections cleanup scheduled", level="info")
        else:
            # Otherwise run it in the event loop
            loop.run_until_complete(projections.close())
            log("Neo4j projections closed", level="info")
    except Exception as e:
        log(f"Error closing Neo4j projections: {e}", level="error")

def error_reporting_cleanup() -> None:
    """Stop periodic error reporting during application shutdown."""
    try:
        ErrorAudit.stop_periodic_reporting()
        log("Error reporting stopped", level="info")
    except Exception as e:
        log(f"Error stopping error reporting: {e}", level="error")

def health_monitor_cleanup() -> None:
    """Stop health monitoring system during application shutdown."""
    try:
        health_monitor = HealthMonitor()
        
        # If we're in an async context, await the coroutine
        if asyncio.get_event_loop().is_running():
            asyncio.create_task(health_monitor.stop_monitoring_async())
        else:
            # Otherwise run it in the event loop
            loop = asyncio.get_event_loop()
            loop.run_until_complete(health_monitor.stop_monitoring_async())
            
        log("Health monitoring stopped", level="info")
    except Exception as e:
        log(f"Error stopping health monitoring: {e}", level="error")

async def _initialize_components():
    """Initialize all application components asynchronously."""
    try:
        # Initialize database pool
        await init_db_pool()
        log("Database pool initialized", level="info")
        
        # Start cache analytics
        start_cache_analytics()
        log("Cache analytics started", level="info")
        
        # Start periodic error reporting
        ErrorAudit.start_periodic_reporting(interval=3600)  # Hourly error reporting
        log("Periodic error reporting started", level="info")
        
        # Start health monitoring system
        health_monitor = HealthMonitor()
        health_monitor.start_monitoring(check_interval=300)  # Check health every 5 minutes
        log("Health monitoring system started", level="info")
        
        # Register database cleanup handler
        register_shutdown_handler(db_cleanup)
        
        # Register Neo4j projections cleanup handler
        register_shutdown_handler(neo4j_projections_cleanup)
        
        # Register error reporting cleanup handler
        register_shutdown_handler(error_reporting_cleanup)
        
        # Register health monitoring cleanup handler
        register_shutdown_handler(health_monitor_cleanup)
        
        # Initialize other components here
        # ...
        
        log("Application components initialized successfully", level="info")
    except Exception as e:
        log(f"Error initializing application components: {e}", level="error")
        raise

def initialize_application():
    """Initialize the application and all its components."""
    try:
        log("Initializing application...", level="info")
        
        # Register the cleanup handler
        atexit.register(_cleanup_on_exit)
        
        # Initialize components asynchronously
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_initialize_components())
        
        log("Application initialized successfully", level="info")
        return True
    except Exception as e:
        log(f"Application initialization failed: {e}", level="error")
        return False

if __name__ == "__main__":
    success = initialize_application()
    if not success:
        sys.exit(1) 