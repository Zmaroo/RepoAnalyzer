"""Application initialization and lifecycle management."""

import asyncio
import atexit
import os
import sys
from typing import Callable, List, Optional

from utils.logger import log
from utils.async_runner import cleanup_tasks
from utils.cache import cache_coordinator
from utils.cache_analytics import start_cache_analytics

# List to keep track of registered shutdown handlers
_shutdown_handlers: List[Callable] = []

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

async def _initialize_components():
    """Initialize all application components asynchronously."""
    try:
        # Start cache analytics
        start_cache_analytics()
        log("Cache analytics started", level="info")
        
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