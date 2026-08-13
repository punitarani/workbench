"""A shared concurrency budget for LM backends.

The windowed engine multiplies in-flight LM calls; the permit pool is the
single throttle they all share. One pool can bound several backends at
once (inject the same pool), and budgets compose by nesting pools.
"""

import asyncio


class PermitPool:
    def __init__(self, limit: int) -> None:
        if limit < 1:
            raise ValueError(f"permit pool needs a positive limit, got {limit}")
        self._limit = limit
        self._semaphore = asyncio.Semaphore(limit)

    @property
    def limit(self) -> int:
        return self._limit

    async def __aenter__(self) -> PermitPool:
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self._semaphore.release()
