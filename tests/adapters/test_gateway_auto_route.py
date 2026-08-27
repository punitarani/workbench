"""An empty pin routes automatically, and says which provider answered.

The gateway exists because a bare model id routes to whatever the account
defaults to, which 404s or silently serves different weights. Every tier is
therefore pinned to named endpoints with `allow_fallbacks` off.

One tier can no longer be served that way. Probed one endpoint at a time,
`moonshotai/mxfp4` returns 404 from this account's guardrail and
`modal/mxfp4` returns 429; of the 16 endpoints OpenRouter lists for the
model, eight answer and none is the pinned quantization. Three consecutive
sweeps died `ApiRateLimitError` on every trial, having measured nothing --
and a rate-limited DNF is indistinguishable downstream from a model that
cannot do the task.

So an EMPTY tuple means route automatically. It has to be distinguishable
from a missing entry, which still means "unsupported model": one is a
decision, the other is a typo, and conflating them would let a misspelled
alias silently reach whatever OpenRouter felt like serving.

The cost is that scores for such a tier no longer come from one guaranteed
set of weights. That is acceptable only if a reader can tell which weights
answered, so the gateway records the `x-generation-id` header -- resolvable
through `GET /api/v1/generation?id=`. A header is not the response body;
the stream is still proxied byte-for-byte.
"""

import json
import logging

import httpx
import pytest

from adapters.harbor_matrix.gateway import GatewayConfig, ProviderGateway
from adapters.harness.openrouter_client import MODEL_PROVIDERS

pytestmark = pytest.mark.anyio


@pytest.fixture
def gateway_config() -> GatewayConfig:
    return GatewayConfig(
        openrouter_api_key="openrouter-host-secret",
        gateway_token="ephemeral-container-secret",
        bind_host="127.0.0.1",
        port=0,
        upstream_url="https://openrouter.test/api/v1/responses",
    )


def _upstream(seen: dict, *, generation_id: str | None = "gen-abc123"):
    async def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads((await request.aread()).decode())
        headers = {"content-type": "application/json"}
        if generation_id is not None:
            headers["x-generation-id"] = generation_id
        return httpx.Response(200, headers=headers, json={"id": "c1", "choices": []})

    return handler


async def _post(gateway_config, seen, model, **kwargs):
    gateway = ProviderGateway(
        gateway_config, upstream_transport=httpx.MockTransport(_upstream(seen, **kwargs))
    )
    async with gateway:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{gateway.local_url}/v1/chat/completions",
                headers={"Authorization": "Bearer ephemeral-container-secret"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                },
            )
    return response, gateway


async def test_the_auto_routed_tier_is_declared_empty_not_missing() -> None:
    """The distinction the gateway relies on, asserted at the source."""

    assert MODEL_PROVIDERS["moonshotai/kimi-k3"] == ()
    assert MODEL_PROVIDERS.get("moonshotai/kimi-k3") is not None


async def test_an_empty_pin_sends_no_provider_block(gateway_config) -> None:
    seen: dict = {}
    response, _ = await _post(gateway_config, seen, "kimi-k3")
    assert response.status_code == 200
    assert seen["body"]["model"] == "moonshotai/kimi-k3"
    # Not an empty order, and not allow_fallbacks -- absent. An empty
    # `order` with fallbacks off is a request no endpoint can satisfy.
    assert "provider" not in seen["body"], seen["body"].get("provider")


async def test_a_named_pin_is_still_enforced(gateway_config) -> None:
    """The change must not relax any tier that can still be pinned."""

    seen: dict = {}
    response, _ = await _post(gateway_config, seen, "opus-5")
    assert response.status_code == 200
    assert seen["body"]["provider"] == {
        "order": ["amazon-bedrock/us-east-1", "amazon-bedrock"],
        "allow_fallbacks": False,
    }


async def test_an_unknown_model_is_still_refused(gateway_config) -> None:
    """Empty means auto; missing must still mean unsupported."""

    seen: dict = {}
    response, _ = await _post(gateway_config, seen, "not-a-model")
    assert response.status_code == 400
    assert "body" not in seen, "an unknown alias reached the upstream"


async def test_the_serving_generation_is_recorded(gateway_config) -> None:
    seen: dict = {}
    _, gateway = await _post(gateway_config, seen, "kimi-k3")
    assert [r.generation_id for r in gateway.provenance] == ["gen-abc123"]


async def test_a_missing_generation_header_is_not_fatal(gateway_config) -> None:
    """Provenance is for the reader; losing it must not fail the request."""

    seen: dict = {}
    response, gateway = await _post(
        gateway_config, seen, "kimi-k3", generation_id=None
    )
    assert response.status_code == 200
    assert [r.generation_id for r in gateway.provenance] == [None]
