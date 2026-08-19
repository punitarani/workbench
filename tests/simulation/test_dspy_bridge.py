import asyncio
from pathlib import Path

import dspy
from pydantic import BaseModel

from core.seed import Seed
from simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from simulation.lm.dspy_lm import WorkbenchLM
from simulation.lm.protocol import LMRequest, LMResponse, TokenUsage


class CannedLM:
    """Returns a fixed completion; counts calls to prove replay hermeticity."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls = 0

    async def complete(self, request: LMRequest) -> LMResponse:
        self.calls += 1
        return LMResponse(
            text=self._text,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
        )


class Verdict(BaseModel):
    label: str
    why: str


class Judge(dspy.Signature):
    """Judge the claim."""

    claim: str = dspy.InputField()
    verdict: Verdict = dspy.OutputField()


CANNED = (
    "[[ ## verdict ## ]]\n"
    '{"label": "plausible", "why": "the claim is consistent"}\n\n'
    "[[ ## completed ## ]]"
)


def make_bridge(inner, seed_root: int = 42) -> WorkbenchLM:
    return WorkbenchLM(
        inner,
        model="deepseek/deepseek-v4-flash-0731",
        seed=Seed(root=seed_root),
        path=("entity", "daniel", "judge"),
        max_tokens=512,
    )


async def test_record_then_replay_is_hermetic(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path / "cassette")
    canned = CannedLM(CANNED)

    recording_bridge = make_bridge(RecordingLM(canned, store))
    predict = dspy.Predict(Judge)
    with dspy.context(lm=recording_bridge):
        recorded = await predict.acall(claim="the sky is blue")
    assert recorded.verdict.label == "plausible"
    assert canned.calls == 1

    replay_bridge = make_bridge(ReplayLM(store))
    with dspy.context(lm=replay_bridge):
        replayed = await predict.acall(claim="the sky is blue")
    assert canned.calls == 1, "replay must not touch the backend"
    assert replayed.verdict == recorded.verdict


async def test_seed_varies_by_call_counter_and_path(tmp_path: Path) -> None:
    seen: list[int] = []

    class SeedSpy:
        async def complete(self, request: LMRequest) -> LMResponse:
            seen.append(request.seed)
            return LMResponse(
                text=CANNED,
                usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
            )

    bridge = make_bridge(SeedSpy())
    predict = dspy.Predict(Judge)
    with dspy.context(lm=bridge):
        await predict.acall(claim="one")
        await predict.acall(claim="two")
    assert len(seen) == 2
    assert seen[0] != seen[1], "each call gets a fresh derived seed"

    fresh_bridge = make_bridge(SeedSpy.__new__(SeedSpy))
    fresh_seen: list[int] = []

    class SeedSpy2:
        async def complete(self, request: LMRequest) -> LMResponse:
            fresh_seen.append(request.seed)
            return LMResponse(
                text=CANNED,
                usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
            )

    fresh_bridge = make_bridge(SeedSpy2())
    with dspy.context(lm=fresh_bridge):
        await predict.acall(claim="one")
    assert fresh_seen[0] == seen[0], "same path + counter -> same seed"


async def test_context_isolates_concurrent_entities() -> None:
    daniel_lm = make_bridge(
        CannedLM(
            "[[ ## verdict ## ]]\n"
            '{"label": "daniel", "why": "d"}\n\n'
            "[[ ## completed ## ]]"
        )
    )
    priya_lm = make_bridge(
        CannedLM(
            "[[ ## verdict ## ]]\n"
            '{"label": "priya", "why": "p"}\n\n'
            "[[ ## completed ## ]]"
        )
    )
    predict = dspy.Predict(Judge)

    async def ask(lm: WorkbenchLM) -> str:
        with dspy.context(lm=lm):
            result = await predict.acall(claim="who are you")
            return result.verdict.label

    labels = await asyncio.gather(ask(daniel_lm), ask(priya_lm))
    assert labels == ["daniel", "priya"]


async def test_dspy_component_invokes_under_own_lm() -> None:
    from simulation.entity.dspy_component import DSPyComponent

    class JudgeState(BaseModel):
        last_label: str = ""

    class JudgeComponent(DSPyComponent):
        state_model = JudgeState

        def __init__(self, lm: WorkbenchLM) -> None:
            super().__init__("judge", module=dspy.Predict(Judge), lm=lm)
            self._state = JudgeState()

        async def judge(self, claim: str) -> str:
            prediction = await self._invoke(claim=claim)
            self._state = JudgeState(last_label=prediction.verdict.label)
            return prediction.verdict.label

        def get_state(self) -> JudgeState:
            return self._state

        def set_state(self, state: JudgeState) -> None:
            self._state = state

    component = JudgeComponent(make_bridge(CannedLM(CANNED)))
    label = await component.judge("claim")
    assert label == "plausible"
    assert component.get_state().last_label == "plausible"
