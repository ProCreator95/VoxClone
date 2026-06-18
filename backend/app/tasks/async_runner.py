from __future__ import annotations

"""
Persistent asyncio event loop for Celery worker processes.

Celery tasks are synchronous; async DB/Redis/FFmpeg helpers run via
run_until_complete on a single loop per worker process. Using asyncio.run()
per task creates a new loop each time, which breaks redis.asyncio clients
connected during worker_process_init on a different loop.
"""

import asyncio
from typing import TypeVar

T = TypeVar("T")

_worker_loop: asyncio.AbstractEventLoop | None = None


def get_worker_event_loop() -> asyncio.AbstractEventLoop:
    """Return (or create) the one event loop used for this worker process."""
    global _worker_loop
    if _worker_loop is None:
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


def run_async(coro: asyncio.coroutines.Coroutine[None, None, T]) -> T:
    """Run an async coroutine on the worker's persistent event loop."""
    return get_worker_event_loop().run_until_complete(coro)
