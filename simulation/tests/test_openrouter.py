import json

import httpx
import pytest

from workbench.simulation.errors import LMResponseError, LMTransportError
from workbench.simulation.lm.openrouter import OpenRouterLM
from workbench.simulation.lm.protocol import ChatMessage, LMRequest


def request(**overrides) -> LMRequest:
    defaults = dict(
        model="deepseek/deepseek-v4-flash-0731",
        messages=(ChatMessage(role="user", content="hello"),),
        temperature=1.0,
        top_p=0.95,
        max_tokens=64,
        seed=7,
    )
    defaults.update(overrides)
    return LMRequest(**defaults)


def make_lm(handler) -> OpenRouterLM:
    transport = httpx.MockTransport(handler)
    return OpenRouterLM(api_key="sk-or-test", transport=transport)


async def test_request_shape_and_response_parsing() -> None:
    seen: dict = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen["auth"] = http_request.headers["authorization"]
        seen["body"] = json.loads(http_request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi there"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )

    lm = make_lm(handler)
    response = await lm.complete(request())
    assert response.text == "hi there"
    assert response.usage.prompt_tokens == 5
    assert response.usage.completion_tokens == 2
    assert not response.cache_hit
    assert seen["auth"] == "Bearer sk-or-test"
    assert seen["body"]["model"] == "deepseek/deepseek-v4-flash-0731"
    assert seen["body"]["seed"] == 7
    assert seen["body"]["temperature"] == 1.0
    assert seen["body"]["top_p"] == 0.95
    assert seen["body"]["max_tokens"] == 64
    assert "response_format" not in seen["body"]


async def test_response_schema_is_forwarded() -> None:
    seen: dict = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(http_request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    lm = make_lm(handler)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    await lm.complete(request(response_schema=schema))
    response_format = seen["body"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"] == schema


async def test_http_error_raises_transport_error() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    lm = make_lm(handler)
    with pytest.raises(LMTransportError) as excinfo:
        await lm.complete(request())
    assert "429" in str(excinfo.value)


async def test_malformed_body_raises_response_error() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    lm = make_lm(handler)
    with pytest.raises(LMResponseError):
        await lm.complete(request())


async def test_reasoning_is_disabled_for_simulation_calls() -> None:
    seen: dict = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(http_request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    lm = make_lm(handler)
    await lm.complete(request())
    assert seen["body"]["reasoning"] == {"enabled": False}


async def test_null_content_raises_response_error() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": None}, "finish_reason": "length"}
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    lm = make_lm(handler)
    with pytest.raises(LMResponseError) as excinfo:
        await lm.complete(request())
    assert "empty completion" in str(excinfo.value)
