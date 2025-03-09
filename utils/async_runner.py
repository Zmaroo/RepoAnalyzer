import asyncio
import threading
import concurrent.futures
from typing import TypeVar, Awaitable, Set, Any
from functools import wraps

from utils.logger import log

T = TypeVar('T')
_global_loop = None
_pending_tasks: Set[asyncio.Task] = set()
_loop_lock = threading.Lock()
_shutdown_event = threading.Event()

def _start_global_loop(loop: asyncio.AbstractEventLoop):
    """
    Set up and run the global event loop forever.
    """
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    finally:
        try:
            # Cancel all pending tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            
            # Allow cancelled tasks to complete with a timeout
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception as e:
            log(f"Error during loop cleanup: {e}", level="error")

def get_loop() -> asyncio.AbstractEventLoop:
    """
    Returns the current running event loop if available.
    Otherwise, it falls back to a global event loop running in a background thread.
    """
    global _global_loop
    
    try:
        # Try to get the loop if called within an async context
        return asyncio.get_running_loop()
    except RuntimeError:
        # No running loop; use or start our global loop
        with _loop_lock:
            if _global_loop is None or _global_loop.is_closed():
                _global_loop = asyncio.new_event_loop()
                t = threading.Thread(target=_start_global_loop, args=(_global_loop,), daemon=True)
                t.start()
            return _global_loop

def submit_async_task(coro: Awaitable[T]) -> concurrent.futures.Future:
    """
    Submit an asynchronous task (a coroutine) to the event loop.
    Creates a task and tracks it to prevent garbage collection and ensure proper handling.
    
    Args:
        coro: The coroutine to run.
        
    Returns:
        A concurrent.futures.Future that will be resolved when the coroutine completes.
    """
    if _shutdown_event.is_set():
        raise RuntimeError("Cannot submit new tasks during shutdown")
        
    loop = get_loop()
    
    # Create and track the task
    task = loop.create_task(coro)
    _pending_tasks.add(task)
    
    def _on_task_done(t):
        try:
            _pending_tasks.remove(t)
            exc = t.exception()
            if exc:
                # Create a new task for logging and add it to pending tasks
                loop = asyncio.get_event_loop()
                log_task = loop.create_task(log(f"Task failed with error: {exc}", level="error"))
                _pending_tasks.add(log_task)
                log_task.add_done_callback(lambda lt: _pending_tasks.remove(lt) if lt in _pending_tasks else None)
        except (asyncio.CancelledError, Exception) as e:
            # Create a new task for error logging
            loop = asyncio.get_event_loop()
            log_task = loop.create_task(log(f"Error in task cleanup: {e}", level="error"))
            _pending_tasks.add(log_task)
            log_task.add_done_callback(lambda lt: _pending_tasks.remove(lt) if lt in _pending_tasks else None)
    
    task.add_done_callback(_on_task_done)
    
    # Convert to a concurrent.futures.Future for compatibility
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future

def cleanup_tasks():
    """
    Cancel all pending tasks and clean up the event loop.
    This should be called during application shutdown.
    """
    global _pending_tasks, _global_loop
    _shutdown_event.set()
    
    if not _pending_tasks:
        return
        
    try:
        loop = get_loop()
        
        # Cancel all pending tasks
        for task in _pending_tasks.copy():
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete with a timeout
        if _pending_tasks:
            cleanup_future = asyncio.gather(*_pending_tasks, return_exceptions=True)
            try:
                loop.run_until_complete(
                    asyncio.wait_for(cleanup_future, timeout=5.0)
                )
            except (asyncio.TimeoutError, Exception) as e:
                log(f"Error or timeout during task cleanup: {e}", level="error")
        
        _pending_tasks.clear()
        
    except Exception as e:
        log(f"Error during task cleanup: {e}", level="error")
    finally:
        # If using global loop, shut it down
        if loop is _global_loop and not loop.is_closed():
            try:
                loop.stop()
                loop.close()
            except Exception as e:
                log(f"Error closing global loop: {e}", level="error") 