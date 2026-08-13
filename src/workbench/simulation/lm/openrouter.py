"""OpenRouter backend: OpenAI-compatible chat completions over httpx."""

from typing import Any

import httpx

from workbench.simulation.errors import LMResponseError, LMTransportError
from workbench.simulation.lm.permits import PermitPool
from workbench.simulation.lm.protocol import LMRequest, LMResponse, TokenUsage

BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-5.6-luna"
# One provider, no fallbacks: routing that silently moves between providers
# changes tokenization and sampling, and a recorded day must replay from the
# same source it was recorded against.
DEFAULT_PROVIDERS = ("openai",)


class OpenRouterLM:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = BASE_URL,
        max_concurrency: int = 8,
        timeout_seconds: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
        providers: tuple[str, ...] = DEFAULT_PROVIDERS,
        permits: PermitPool | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
            transport=transport,
        )
        # Inject a shared pool to bound several backends with one budget;
        # by default each backend gets a private pool of max_concurrency.
        self._permits = permits if permits is not None else PermitPool(max_concurrency)
        self._providers = providers

    async def complete(self, request: LMRequest) -> LMResponse:
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
            "max_tokens": request.max_tokens,
            "seed": request.seed,
            # Reasoning modes can return completions whose content is empty
            # (tokens spent thinking); simulation turns want plain answers.
            "reasoning": {"enabled": False},
        }
        if self._providers:
            body["provider"] = {
                "order": list(self._providers),
                "allow_fallbacks": False,
            }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.top_p is not None:
            body["top_p"] = request.top_p
        if request.response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "strict": True,
                    "schema": request.response_schema,
                },
            }

        async with self._permits:
            try:
                http_response = await self._client.post("/chat/completions", json=body)
            except httpx.HTTPError as error:
                raise LMTransportError(f"openrouter request failed: {error}") from error

        if http_response.status_code != 200:
            raise LMTransportError(
                f"openrouter returned {http_response.status_code}: "
                f"{http_response.text[:500]}"
            )

        try:
            data = http_response.json()
            choice = data["choices"][0]
            text = choice["message"]["content"]
            if not text:
                finish = choice.get("finish_reason", "unknown")
                raise LMResponseError(
                    f"empty completion (finish_reason={finish}); the model "
                    "may have spent its budget on reasoning tokens"
                )
            usage = data.get("usage", {})
            return LMResponse(
                text=text,
                usage=TokenUsage(
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                ),
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise LMResponseError(
                f"unexpected openrouter response shape: {http_response.text[:500]}"
            ) from error

    async def close(self) -> None:
        await self._client.aclose()
