"""Cross-platform Playwright runner for Windows + uvicorn compatibility.

On Windows, uvicorn --reload forces SelectorEventLoop which does not
support asyncio.create_subprocess_exec(). Playwright needs subprocess
support to communicate with the browser.

This module runs Playwright in a dedicated thread with its own
ProactorEventLoop, returning results to the calling async context.
"""
import asyncio
import sys
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import TypeVar, Callable, Coroutine, Any, Dict
from urllib.parse import urlparse

logger = logging.getLogger("playwright-runner")

T = TypeVar("T")

# Shared thread pool for Playwright work (single thread to avoid
# multiple browser processes competing for resources).
_playwright_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

_NEEDS_THREAD_WORKAROUND = sys.platform == "win32"


def _run_in_proactor_loop(coro_fn: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Runs an async function in a fresh ProactorEventLoop.

    Called inside a thread where no event loop is running.
    """
    loop = asyncio.new_event_loop()
    if sys.platform == "win32":
        # ProactorEventLoop supports subprocess creation on Windows
        loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_fn())
    finally:
        loop.close()


async def run_playwright(coro_fn: Callable[[], Coroutine[Any, Any, T]]) -> T:
    """Runs a Playwright async function with subprocess support.

    On Windows (where uvicorn's SelectorEventLoop lacks subprocess
    support), delegates to a background thread with ProactorEventLoop.
    On Linux/macOS, runs directly in the current event loop.

    Usage:
        async def my_playwright_work():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                ...
                return result

        result = await run_playwright(my_playwright_work)
    """
    if not _NEEDS_THREAD_WORKAROUND:
        return await coro_fn()

    logger.debug("Delegating Playwright work to ProactorEventLoop thread")
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _playwright_executor,
        lambda: _run_in_proactor_loop(coro_fn)
    )


# Per-host concurrency control.
#
# Multiple pipeline runs can target the same site concurrently. Even though
# Playwright work is already serialized through the single-worker executor
# above, we still guard against hammering a single target host (a common
# trigger for HTTP 429 rate limiting) with an explicit per-host slot. Locks
# are created lazily and keyed by network location, so unrelated targets are
# unaffected.
_host_slots: Dict[str, asyncio.Lock] = {}


def _host_key(url: str) -> str:
    try:
        parsed = urlparse(url or "")
        return parsed.netloc or (url or "default")
    except Exception:
        return url or "default"


@asynccontextmanager
async def target_slot(url: str):
    """Async context manager serializing browser work against one host.

    Acquire this around any ``run_playwright(...)`` call that drives a browser
    against ``url`` so that concurrent runs cannot pile requests onto the same
    target simultaneously.
    """
    key = _host_key(url)
    lock = _host_slots.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _host_slots[key] = lock
    async with lock:
        yield
