"""Budget enforcement that fails loud instead of degrading into garbage."""

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
        self.usage = TokenUsage(prompt_tokens=0, completion_tokens=0)

    async def complete(self, request: LMRequest) -> LMResponse:
        if self._calls >= self._max_calls:
            raise LMBudgetExceededError(
                f"budget of {self._max_calls} calls exhausted"
            )
        self._calls += 1
        response = await self._inner.complete(request)
        self.usage = self.usage + response.usage
        return response
