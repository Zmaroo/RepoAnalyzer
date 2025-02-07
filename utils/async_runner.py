import asyncio
import threading

_loop = asyncio.new_event_loop()

def start_loop():
    asyncio.set_event_loop(_loop)
    _loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

def submit_async_task(coro):
    return asyncio.run_coroutine_threadsafe(coro, _loop) 