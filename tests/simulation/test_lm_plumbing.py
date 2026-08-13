"""R0 plumbing: retry semantics, the network-vs-total budget split, the
engine's batch observability hook, and the telemetry writer."""

from pathlib import Path

import pytest
from toy_scenario import build_engine

from workbench.simulation.engine.engine import StopCondition
from workbench.simulation.errors import (
    LMBudgetExceededError,
    LMResponseError,
    LMTransportError,
)
from workbench.simulation.lm.budget import BudgetedLM
from workbench.simulation.lm.protocol import (
    ChatMessage,
    LMRequest,
    LMResponse,
    TokenUsage,
)
from workbench.simulation.lm.retry import RetryLM
from workbench.simulation.telemetry import (
    DayRow,
    SegmentRow,
    TelemetryWriter,
    read_rows,
)


def _request(seed: int = 1) -> LMRequest:
    return LMRequest(
        model="test/model",
        messages=(ChatMessage(role="user", content="hi"),),
        max_tokens=8,
        seed=seed,
    )


def _response(*, cache_hit: bool = False) -> LMResponse:
    return LMResponse(
        text="ok",
        usage=TokenUsage(prompt_tokens=3, completion_tokens=1),
        cache_hit=cache_hit,
    )


class FlakyLM:
    def __init__(self, failures: int, error: type[Exception] = LMTransportError):
        self.failures = failures
        self.error = error
        self.attempts = 0

    async def complete(self, request: LMRequest) -> LMResponse:
        self.attempts += 1
        if self.attempts <= self.failures:
            raise self.error("transient")
        return _response()


async def test_retry_recovers_from_transient_transport_errors() -> None:
    inner = FlakyLM(failures=2)
    lm = RetryLM(inner, attempts=4, base_delay=0.0)
    response = await lm.complete(_request())
    assert response.text == "ok"
    assert inner.attempts == 3


async def test_retry_exhausts_and_raises() -> None:
    inner = FlakyLM(failures=99)
    lm = RetryLM(inner, attempts=3, base_delay=0.0)
    with pytest.raises(LMTransportError):
        await lm.complete(_request())
    assert inner.attempts == 3


async def test_retry_never_retries_response_errors() -> None:
    inner = FlakyLM(failures=99, error=LMResponseError)
    lm = RetryLM(inner, attempts=5, base_delay=0.0)
    with pytest.raises(LMResponseError):
        await lm.complete(_request())
    assert inner.attempts == 1, "a malformed response is not a transport blip"


class HitOrMissLM:
    """Serves cache hits until told otherwise."""

    def __init__(self) -> None:
        self.hits = True

    async def complete(self, request: LMRequest) -> LMResponse:
        return _response(cache_hit=self.hits)


async def test_budget_gates_network_calls_only() -> None:
    inner = HitOrMissLM()
    budgeted = BudgetedLM(inner, max_calls=1)
    for seed in range(5):
        await budgeted.complete(_request(seed))
    assert budgeted.calls == 5
    assert budgeted.network_calls == 0, "cassette hits never spend budget"

    inner.hits = False
    await budgeted.complete(_request(10))
    assert budgeted.network_calls == 1
    with pytest.raises(LMBudgetExceededError):
        await budgeted.complete(_request(11))

    inner.hits = True
    with pytest.raises(LMBudgetExceededError):
        await budgeted.complete(_request(12))


async def test_on_batch_sees_every_step(tmp_path: Path) -> None:
    batches: list[int] = []
    engine, writer = build_engine(tmp_path / "world.jsonl")
    try:
        result = await engine.run(
            StopCondition(max_steps=6),
            on_batch=lambda results: batches.append(len(results)),
        )
    finally:
        writer.close()
    assert sum(batches) == result.steps
    assert all(size >= 1 for size in batches)


def test_telemetry_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.jsonl"
    writer = TelemetryWriter(path)
    writer.append(
        DayRow(
            day="2026-01-05",
            day_index=0,
            steps=120,
            events={"email.message": 40, "sim.wake": 60},
            lm_calls=150,
            lm_network_calls=90,
            prompt_tokens=200_000,
            completion_tokens=12_000,
            rejections=2,
            batches=30,
            max_batch=9,
            wall_seconds=412.5,
        )
    )
    writer.append(SegmentRow(label="interrupt", day="2026-01-05", reason="sigint"))
    rows = list(read_rows(path))
    assert len(rows) == 2
    assert isinstance(rows[0], DayRow)
    assert rows[0].events["email.message"] == 40
    assert isinstance(rows[1], SegmentRow)
    assert rows[1].label == "interrupt"
    assert list(read_rows(tmp_path / "absent.jsonl")) == []
