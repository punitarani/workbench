"""The typed language-model contract every backend implements.

``seed`` is required, not optional: every call site must thread one, which is
what makes recorded runs reproducible.
"""

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class LMRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str
    messages: tuple[ChatMessage, ...] = Field(min_length=1)
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int = Field(gt=0)
    seed: int = Field(ge=0)
    response_schema: dict[str, Any] | None = None
    # Distinguishes intentional resamples of an otherwise identical request.
    rollout_id: int = Field(default=0, ge=0)


class TokenUsage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )


class LMResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    usage: TokenUsage
    cache_hit: bool = False


class LanguageModel(Protocol):
    async def complete(self, request: LMRequest) -> LMResponse: ...
