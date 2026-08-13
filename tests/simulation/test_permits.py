"""The permit pool: one shared concurrency budget across LM backends."""

import asyncio

import httpx

from workbench.simulation.lm.openrouter import OpenRouterLM
from workbench.simulation.lm.permits import PermitPool
from workbench.simulation.lm.protocol import ChatMessage, LMRequest


async def test_pool_bounds_concurrency() -> None:
    pool = PermitPool(2)
    active = 0
    peak = 0

    async def task() -> None:
        nonlocal active, peak
        async with pool:
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1

    await asyncio.gather(*(task() for _ in range(6)))
    assert peak == 2
    assert pool.limit == 2


async def test_two_backends_share_one_pool() -> None:
    pool = PermitPool(1)
    active = 0
    peak = 0

    class Probe(httpx.AsyncBaseTransport):
        async def handle_async_request(
            self, request: httpx.Request
        ) -> httpx.Response:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
            )

    lms = [
        OpenRouterLM(api_key="k", transport=Probe(), permits=pool) for _ in range(2)
    ]
    request = LMRequest(
        model="test/model",
        messages=(ChatMessage(role="user", content="hi"),),
        max_tokens=8,
        seed=1,
    )
    responses = await asyncio.gather(
        *(lm.complete(request) for lm in lms for _ in range(3))
    )
    assert all(r.text == "ok" for r in responses)
    assert peak == 1, "a shared pool must serialize across backends"
    for lm in lms:
        await lm.close()
