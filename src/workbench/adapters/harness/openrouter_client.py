"""OpenRouter chat-completions client implementing the ChatClient protocol.

Fail-loud: any non-200 response or body without ``choices[0].message``
raises. Usage accumulates on the client across calls so a whole eval run
reports one prompt/completion total; ``usage_cost`` prices it.
"""

from typing import Any

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(RuntimeError):
    """OpenRouter returned a non-200 status or a malformed body."""


# Routing pins for the eval matrix, in priority order, no fallbacks
# outside the list. Verified against the live API: a vendor prefix is not
# always a valid slug (deepseek's own is not served on this account), so
# these are recorded per model rather than derived.
MODEL_PROVIDERS: dict[str, tuple[str, ...]] = {
    # The sign-off models, pinned to the only first-party-grade endpoints this
    # key's provider guardrail permits. The direct "anthropic" and "openai"
    # tags are blocked for this account -- pinning to them returns 404 "no
    # endpoints found" rather than falling back, which would fail a paid batch
    # nine tasks deep. Bedrock and Azure serve the same weights, so the scores
    # stay reproducible; a quantized community replica would not.
    # The bare amazon-bedrock tag routes to whichever Bedrock endpoint
    # OpenRouter ranks first; when that endpoint is deranked it stalls with
    # keep-alive whitespace instead of erroring. Pin the healthy region first
    # and keep the bare tag as the recovery fallback.
    "anthropic/claude-opus-5": ("amazon-bedrock/us-east-1", "amazon-bedrock"),
    # Azure, and only Azure. OpenRouter serves this model from `openai` and
    # `azure` alone -- there is no Bedrock endpoint, and the `openai` tag is
    # blocked by this account's data-policy guardrail (404 "No endpoints
    # available matching your guardrail restrictions").
    #
    # Do not read tool support off the endpoint listing's
    # supported_parameters: it omits `tools` for azure, and azure accepts a
    # tools payload and answers correctly anyway. Checked directly.
    "openai/gpt-5.6-sol": ("azure",),
    "openai/gpt-5.6-luna": ("openai",),
    "z-ai/glm-5.2": (
        "baidu/fp8",
        "novita/fp8",
        "streamlake/fp8",
    ),
    "deepseek/deepseek-v4-flash-0731": (
        "baidu/fp8",
        "gmicloud/fp8",
        "baseten/fp8",
    ),
}


class OpenRouterChatClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        *,
        providers: tuple[str, ...] = (),
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        # Pinning routing to named providers keeps a matrix reproducible:
        # OpenRouter otherwise load-balances across hosts that tokenize and
        # sample differently. Slugs are per-model (a vendor prefix is not
        # always a valid provider), so this is explicit, never derived.
        self.providers = providers
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0),
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }
        if self.providers:
            payload["provider"] = {
                "order": list(self.providers),
                "allow_fallbacks": False,
            }
        response = await self._client.post(OPENROUTER_URL, json=payload)
        if response.status_code != 200:
            raise OpenRouterError(
                f"OpenRouter returned {response.status_code}: {response.text[:500]}"
            )
        try:
            body = response.json()
            message = body["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise OpenRouterError(
                f"malformed OpenRouter response: {error}: {response.text[:500]}"
            ) from error
        usage = body.get("usage") or {}
        self.prompt_tokens += int(usage.get("prompt_tokens", 0))
        self.completion_tokens += int(usage.get("completion_tokens", 0))
        return message

    def usage_cost(self, prices_per_mtok: tuple[float, float]) -> float:
        """Accumulated cost in USD given (prompt, completion) prices per Mtok."""
        prompt_price, completion_price = prices_per_mtok
        return (
            self.prompt_tokens * prompt_price
            + self.completion_tokens * completion_price
        ) / 1_000_000

    async def aclose(self) -> None:
        await self._client.aclose()
