"""Deterministic no-network backend for tests and dry runs."""

from collections.abc import Mapping

from simulation.lm.cassette import cassette_key
from simulation.lm.protocol import LMRequest, LMResponse, TokenUsage


class FakeLM:
    """Response is a pure function of the request key and the fake seed."""

    def __init__(
        self, *, fake_seed: int = 0, responses: Mapping[str, str] | None = None
    ) -> None:
        self._fake_seed = fake_seed
        self._responses = dict(responses or {})

    async def complete(self, request: LMRequest) -> LMResponse:
        key = cassette_key(request)
        text = self._responses.get(key, f"fake:{self._fake_seed}:{key[:16]}")
        return LMResponse(
            text=text,
            usage=TokenUsage(
                prompt_tokens=sum(len(m.content) // 4 + 1 for m in request.messages),
                completion_tokens=len(text) // 4 + 1,
            ),
        )
