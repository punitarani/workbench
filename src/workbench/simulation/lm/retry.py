"""Retry transient transport failures.

Sits between a recording layer and the network backend: replay runs
never construct this, because a cassette hit involves no network at all.
Only :class:`LMTransportError` retries — a malformed response
(:class:`LMResponseError`) is a bug or a provider fault that backoff
cannot fix, and it fails loud immediately.
"""

import asyncio
import random

from workbench.simulation.errors import LMTransportError
from workbench.simulation.lm.protocol import LanguageModel, LMRequest, LMResponse


class RetryLM:
    def __init__(
        self,
        inner: LanguageModel,
        *,
        attempts: int = 6,
        base_delay: float = 2.0,
        max_delay: float = 30.0,
    ) -> None:
        if attempts < 1:
            raise ValueError(f"attempts must be positive, got {attempts}")
        self._inner = inner
        self._attempts = attempts
        self._base_delay = base_delay
        self._max_delay = max_delay

    async def complete(self, request: LMRequest) -> LMResponse:
        for attempt in range(self._attempts):
            try:
                return await self._inner.complete(request)
            except LMTransportError:
                if attempt + 1 == self._attempts:
                    raise
                delay = min(self._base_delay * 2**attempt, self._max_delay)
                if delay > 0:
                    delay += random.uniform(0.0, delay / 4)
                await asyncio.sleep(delay)
        raise AssertionError("unreachable")
