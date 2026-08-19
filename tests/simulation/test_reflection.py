"""C3: the day chain mints reflection turns, the actor consolidates the
day through the deep model, and unparseable reflections degrade to a
minimal note instead of failing the day."""

from pathlib import Path

from mini_workplace import make_spec
from test_cohort_ladder import _day_started, _gm, _plan
from test_workplace import DECIDE_IDLE_FALLBACK, SequenceLM

from core.seed import Seed
from core.worldlog import read_events, validate_events
from simulation.run import run_workplace

REFLECT_COMPLETION = (
    "[[ ## reflection ## ]]\n"
    '{"bullets": [{"text": "Kept the inbox clear", '
    '"importance": 4, "refs": []}], '
    '"open_loops": ["confirm tomorrow\'s call"]}\n'
    "\n[[ ## completed ## ]]"
)


async def test_day_chain_mints_reflection_cohort() -> None:
    intervals = {f"p{i}": 60 for i in range(5)}
    gm = _gm(_plan(intervals))
    drafts = await gm.consequences(_day_started())
    reflections = [d for d in drafts if d.tag == "sim.reflection"]
    assert len(reflections) == 5, "one reflection per persona"
    delays = {int(d.delay) for d in reflections}
    assert len(delays) == 1, "reflections share one tick and batch"
    (delay,) = delays
    end_of_day = 17 * 3600 + 1800
    assert delay == end_of_day - 30 * 60
    ends = [d for d in drafts if d.tag == "sim.day.ended"]
    assert int(ends[0].delay) > delay, "reflection lands before day end"


async def test_reflection_becomes_memory_event(tmp_path: Path) -> None:
    """A full mini day: the reflection turn produces a grounded
    sim.agent.memory event even when the model output cannot parse."""

    result = await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=tmp_path / "run",
        inner_lm=SequenceLM([DECIDE_IDLE_FALLBACK]),
        model="test/model",
    )
    assert result.reason in ("quiescent", "end_time")
    events = read_events(tmp_path / "run" / "world.jsonl")
    assert validate_events(events).ok

    reflections = [e for e in events if e.tag == "sim.reflection"]
    notes = [e for e in events if e.tag == "sim.agent.memory"]
    assert reflections, "the chain scheduled a reflection turn"
    assert notes, "the turn produced a persistent memory event"
    assert notes[0].payload.note_kind == "daily_summary"
    assert notes[0].payload.bullets[0].text == "(reflection unavailable)", (
        "canned decide text cannot parse as a reflection; the fallback holds"
    )


class SwitchLM:
    """Serves the reflection completion to reflection prompts and the
    idle decide completion to everything else."""

    def __init__(self) -> None:
        self._inner_idle = SequenceLM([DECIDE_IDLE_FALLBACK])
        self._inner_reflect = SequenceLM([REFLECT_COMPLETION])

    async def complete(self, request):
        prompt = request.messages[-1].content
        if "today_activity" in prompt:
            return await self._inner_reflect.complete(request)
        return await self._inner_idle.complete(request)


async def test_parseable_reflection_carries_model_bullets(tmp_path: Path) -> None:
    """When the model's reflection parses, its bullets land verbatim."""

    result = await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=tmp_path / "run",
        inner_lm=SwitchLM(),
        model="test/model",
    )
    assert result.reason in ("quiescent", "end_time")
    events = read_events(tmp_path / "run" / "world.jsonl")
    notes = [e for e in events if e.tag == "sim.agent.memory"]
    assert notes
    assert notes[0].payload.bullets[0].text == "Kept the inbox clear"
    assert notes[0].payload.open_loops == ("confirm tomorrow's call",)
