"""Budget enforcement that fails loud instead of degrading into garbage.

The budget gates *network* calls: a cassette hit costs nothing and must
never exhaust a recording budget, or resuming a half-recorded run would
charge the whole prefix a second time. Total calls are still counted for
telemetry.
"""

from workbench.simulation.errors import LMBudgetExceededError
from workbench.simulation.lm.protocol import (
    LanguageModel,
    LMRequest,
    LMResponse,
    TokenUsage,
)


class BudgetedLM:
    def __init__(self, inner: LanguageModel, *, max_calls: int) -> None:
        self._inner = inner
        self._max_calls = max_calls
        self._calls = 0
        self._network_calls = 0
        self.usage = TokenUsage(prompt_tokens=0, completion_tokens=0)

    @property
    def calls(self) -> int:
        """Every completion served, cassette hits included."""

        return self._calls

    @property
    def network_calls(self) -> int:
        """Completions that actually reached a backend."""

        return self._network_calls

    async def complete(self, request: LMRequest) -> LMResponse:
        if self._network_calls >= self._max_calls:
            raise LMBudgetExceededError(f"budget of {self._max_calls} calls exhausted")
        response = await self._inner.complete(request)
        self._calls += 1
        if not response.cache_hit:
            self._network_calls += 1
        self.usage = self.usage + response.usage
        return response
