import asyncio
import threading
import concurrent.futures

_global_loop = None

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

def submit_async_task(coro: asyncio.coroutine) -> concurrent.futures.Future:
    """
    Submit an asynchronous task (a coroutine) to the event loop.
    It returns a concurrent.futures.Future.
    """
    loop = get_loop()
    return asyncio.run_coroutine_threadsafe(coro, loop) 