"""Narrow asynchronous cleanup helpers for CLI process shutdown."""

from __future__ import annotations

import asyncio
import logging


logger = logging.getLogger(__name__)
_LITELLM_SERVICE_LOGGING_HOOK = "ServiceLogging.async_service_success_hook"


async def drain_litellm_service_logging_tasks(*, timeout_seconds: float = 2.0) -> int:
    """Finish LiteLLM's detached success hooks before closing a CLI event loop.

    Only the named LiteLLM service-logging hook is handled here. Application
    tasks retain their normal lifecycle and cancellation semantics.
    """
    current_task = asyncio.current_task()
    service_logging_tasks = []
    for task in asyncio.all_tasks():
        if task is current_task or task.done():
            continue
        coroutine = task.get_coro()
        qualname = getattr(coroutine, "__qualname__", "")
        if qualname.endswith(_LITELLM_SERVICE_LOGGING_HOOK):
            service_logging_tasks.append(task)

    if not service_logging_tasks:
        return 0

    _done, pending = await asyncio.wait(service_logging_tasks, timeout=timeout_seconds)
    if pending:
        logger.warning(
            "Cancelling %d pending LiteLLM service-logging task(s) after %.1fs shutdown grace period",
            len(pending),
            timeout_seconds,
        )
        for task in pending:
            task.cancel()

    await asyncio.gather(*service_logging_tasks, return_exceptions=True)
    return len(service_logging_tasks)
