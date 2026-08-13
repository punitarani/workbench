from pathlib import Path

import pytest

from workbench.simulation.errors import (
    CassetteMissError,
    LMBudgetExceededError,
)
from workbench.simulation.lm.budget import BudgetedLM
from workbench.simulation.lm.cassette import (
    CallSite,
    CassetteStore,
    RecordingLM,
    ReplayLM,
    cassette_key,
)
from workbench.simulation.lm.fake import FakeLM
from workbench.simulation.lm.protocol import (
    ChatMessage,
    LMRequest,
    LMResponse,
    TokenUsage,
)


def request(**overrides) -> LMRequest:
    defaults = dict(
        model="deepseek/deepseek-v4-flash-0731",
        messages=(
            ChatMessage(role="system", content="You are Daniel Reyes."),
            ChatMessage(role="user", content="Draft a reply."),
        ),
        temperature=1.0,
        top_p=0.95,
        max_tokens=2048,
        seed=1234,
    )
    defaults.update(overrides)
    return LMRequest(**defaults)


class CountingLM:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.calls = 0

    async def complete(self, req: LMRequest) -> LMResponse:
        self.calls += 1
        return await self.inner.complete(req)


def test_cassette_key_is_stable_and_sensitive() -> None:
    base = cassette_key(request())
    assert base == cassette_key(request())
    assert len(base) == 64
    assert base != cassette_key(request(seed=1235))
    assert base != cassette_key(request(rollout_id=1))
    assert base != cassette_key(request(model="other/model"))
    assert base != cassette_key(
        request(messages=(ChatMessage(role="user", content="x"),))
    )


async def test_fake_lm_is_deterministic() -> None:
    fake = FakeLM()
    first = await fake.complete(request())
    second = await fake.complete(request())
    assert first == second
    assert first.text
    other_request = await fake.complete(request(seed=9))
    assert other_request.text != first.text


async def test_fake_lm_scripted_responses() -> None:
    req = request()
    fake = FakeLM(responses={cassette_key(req): "scripted"})
    assert (await fake.complete(req)).text == "scripted"


async def test_record_then_replay_is_hermetic(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path / "cassette")
    counting = CountingLM(FakeLM())
    recorder = RecordingLM(counting, store)

    req = request()
    recorded = await recorder.complete(req)
    assert counting.calls == 1
    again = await recorder.complete(req)
    assert counting.calls == 1, "second call must come from the cassette"
    assert again.text == recorded.text
    assert again.cache_hit

    replay = ReplayLM(store)
    replayed = await replay.complete(req)
    assert replayed.text == recorded.text
    assert replayed.cache_hit


async def test_replay_miss_raises(tmp_path: Path) -> None:
    replay = ReplayLM(CassetteStore(tmp_path / "cassette"))
    with pytest.raises(CassetteMissError):
        await replay.complete(request())


async def test_cassette_entry_carries_call_site(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path / "cassette")
    site = CallSite(
        entity="daniel", program="ProfessionalActor", predictor="draft_email"
    )
    recorder = RecordingLM(FakeLM(), store, site=site)
    req = request()
    await recorder.complete(req)
    entry = store.read_entry(cassette_key(req))
    assert entry.site == site
    assert entry.request == req


async def test_budget_raises_past_limit() -> None:
    budgeted = BudgetedLM(FakeLM(), max_calls=2)
    await budgeted.complete(request(seed=1))
    await budgeted.complete(request(seed=2))
    with pytest.raises(LMBudgetExceededError):
        await budgeted.complete(request(seed=3))


async def test_usage_accumulates() -> None:
    budgeted = BudgetedLM(FakeLM(), max_calls=10)
    await budgeted.complete(request(seed=1))
    await budgeted.complete(request(seed=2))
    assert budgeted.usage.prompt_tokens > 0
    assert budgeted.usage.completion_tokens > 0


def test_token_usage_addition() -> None:
    total = TokenUsage(prompt_tokens=3, completion_tokens=4) + TokenUsage(
        prompt_tokens=10, completion_tokens=1
    )
    assert total == TokenUsage(prompt_tokens=13, completion_tokens=5)
