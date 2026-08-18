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
from typing import TypeVar, Callable, Coroutine, Any

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
