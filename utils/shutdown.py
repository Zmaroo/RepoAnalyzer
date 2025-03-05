"""Shutdown handler registration and management."""

import asyncio
from typing import Callable, List, Set
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary

# List to keep track of registered shutdown handlers
_shutdown_handlers: List[Callable] = []
_pending_tasks: Set[asyncio.Task] = set()

def register_shutdown_handler(handler: Callable) -> None:
    """Register a function to be called during application shutdown."""
    _shutdown_handlers.append(handler)

@handle_async_errors
async def execute_shutdown_handlers() -> None:
    """Execute all registered shutdown handlers."""
    log("Application shutting down, performing cleanup...", level="info")
    
    # Execute all registered shutdown handlers
    for handler in _shutdown_handlers:
        try:
            if asyncio.iscoroutinefunction(handler):
                # Create task for async handlers
                task = asyncio.create_task(handler())
                _pending_tasks.add(task)
                try:
                    await task
                finally:
                    _pending_tasks.remove(task)
            else:
                handler()
        except Exception as e:
            log(f"Error in shutdown handler: {e}", level="error")
    
    # Clean up any remaining tasks
    if _pending_tasks:
        for task in _pending_tasks:
            task.cancel()
        await asyncio.gather(*_pending_tasks, return_exceptions=True)
        _pending_tasks.clear()
    
    log("Cleanup completed", level="info") 