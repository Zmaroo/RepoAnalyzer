import asyncio
import threading
import concurrent.futures
from typing import TypeVar, Awaitable, Set, Any

T = TypeVar('T')
_global_loop = None
_pending_tasks: Set[asyncio.Task] = set()

def _start_global_loop(loop: asyncio.AbstractEventLoop):
    """
    Set up and run the global event loop forever.
    """
    asyncio.set_event_loop(loop)
    loop.run_forever()

def get_loop() -> asyncio.AbstractEventLoop:
    """
    Returns the current running event loop if available.
    Otherwise, it falls back to a global event loop running in a background thread.
    """
    try:
        # Try to get the loop if called within an async context.
        return asyncio.get_running_loop()
    except RuntimeError:
        # No running loop; use or start our global loop.
        global _global_loop
        if _global_loop is None:
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
    loop = get_loop()
    
    # Create and track the task to prevent garbage collection
    task = loop.create_task(coro)
    global _pending_tasks
    _pending_tasks.add(task)
    
    # Ensure the task is removed from tracking when done
    def _on_task_done(t):
        if t in _pending_tasks:
            _pending_tasks.remove(t)
    
    task.add_done_callback(_on_task_done)
    
    # Convert to a concurrent.futures.Future for compatibility
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future

def cleanup_tasks():
    """
    Cancel all pending tasks and clean up the event loop.
    This should be called during application shutdown.
    """
    global _pending_tasks
    for task in _pending_tasks:
        if not task.done():
            task.cancel()
    
    # Wait for all tasks to complete with a timeout
    if _pending_tasks and _global_loop:
        try:
            future = asyncio.gather(*_pending_tasks, return_exceptions=True)
            _global_loop.call_soon_threadsafe(lambda: asyncio.ensure_future(future))
        except Exception:
            pass 