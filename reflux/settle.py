"""Calling user code from the delivery loop (ADR 0002).

A handler may be written as `async def` and await what it needs, or as a plain function. Both are
correct, and the difference between them is only where the work runs:

- `async def` — awaited on the loop, so an `await db.fetch()` suspends this connection and nobody
  else's.
- a plain function — run on a worker thread (`asyncio.to_thread`), so a blocking call inside it
  stalls that thread only. This is the rule that makes "no blocking on the loop" true by
  construction rather than by review.

A plain function that returns an awaitable is awaited too: writing `async def` is a matter of taste,
not of wiring.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable


async def maybe(fn: Callable[..., Any], *args: Any) -> Any:
    """Call `fn(*args)`: await it if it is a coroutine, otherwise run it off the loop."""
    if inspect.iscoroutinefunction(fn):
        return await fn(*args)
    result = await asyncio.to_thread(fn, *args)
    if inspect.isawaitable(result):
        return await result
    return result
