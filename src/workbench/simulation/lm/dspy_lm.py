"""WorkbenchLM: the bridge from DSPy's typed LM contract onto our LM chain.

DSPy modules run against this instead of dspy.LM, which keeps litellm out of
the transport path entirely. The bridge injects the seed DSPy does not carry:
each call derives one from the entity's seed path plus a call counter, so a
fresh bridge replays the same sequence of seeds — and therefore the same
cassette keys — as the recording run.
"""

from typing import Any

import dspy
from pydantic import BaseModel

from workbench.core.seed import Seed, derive_seed
from workbench.simulation.lm.protocol import (
    ChatMessage,
    LanguageModel,
    LMRequest,
)

_ROLE_MAP = {
    "system": "system",
    "developer": "system",
    "user": "user",
    "assistant": "assistant",
}


def _message_text(message: dspy.LMMessage) -> str:
    parts = [
        part.text for part in message.parts if getattr(part, "text", None) is not None
    ]
    return "\n".join(parts)


def _response_schema(response_format: Any) -> dict[str, Any] | None:
    if response_format is None:
        return None
    if isinstance(response_format, dict):
        return response_format
    if isinstance(response_format, type) and issubclass(response_format, BaseModel):
        return response_format.model_json_schema()
    return None


class WorkbenchLM(dspy.BaseLM):
    forward_contract = "typed_lm"

    def __init__(
        self,
        inner: LanguageModel,
        *,
        model: str,
        seed: Seed,
        path: tuple[str, ...],
        temperature: float | None = 1.0,
        top_p: float | None = 0.95,
        max_tokens: int = 4096,
    ) -> None:
        super().__init__(model=model, cache=False)
        self._inner = inner
        self._seed = seed
        self._path = path
        self._temperature = temperature
        self._top_p = top_p
        self._max_tokens = max_tokens
        self._calls = 0


    @property
    def calls(self) -> int:
        return self._calls

    def set_calls(self, calls: int) -> None:
        """Restore the per-entity call counter on resume; seeds and
        therefore cassette keys continue the recorded sequence."""
        self._calls = calls

    def _to_request(self, request: dspy.LMRequest) -> LMRequest:
        messages = tuple(
            ChatMessage(
                role=_ROLE_MAP.get(message.role, "user"),
                content=_message_text(message),
            )
            for message in request.messages
        )
        call_seed = derive_seed(self._seed, *self._path, f"call-{self._calls}")
        self._calls += 1
        config = request.config
        return LMRequest(
            model=self.model,
            messages=messages,
            temperature=(
                config.temperature
                if config.temperature is not None
                else self._temperature
            ),
            top_p=config.top_p if config.top_p is not None else self._top_p,
            max_tokens=(
                config.max_tokens if config.max_tokens is not None else self._max_tokens
            ),
            seed=call_seed,
            response_schema=_response_schema(config.response_format),
        )

    def forward(self, request: dspy.LMRequest) -> dspy.LMResponse:
        raise NotImplementedError(
            "WorkbenchLM is async-only; drive DSPy modules with acall()"
        )

    async def aforward(self, request: dspy.LMRequest) -> dspy.LMResponse:
        our_request = self._to_request(request)
        our_response = await self._inner.complete(our_request)
        return dspy.LMResponse.from_text(
            our_response.text,
            model=self.model,
            usage={
                "prompt_tokens": our_response.usage.prompt_tokens,
                "completion_tokens": our_response.usage.completion_tokens,
            },
            cache_hit=our_response.cache_hit,
        )
