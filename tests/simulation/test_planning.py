"""C4: morning planning turns — minted first, grounded as plans, rendered
into decide, with a deterministic replan trigger."""

from pathlib import Path

from mini_workplace import make_spec
from test_cohort_ladder import _day_started, _gm, _plan
from test_workplace import DECIDE_IDLE_FALLBACK, SequenceLM

from workbench.core.events import Event
from workbench.core.events.agent import (
    MemoryBullet,
    PlanBlock,
    SimAgentPlanPayload,
)
from workbench.core.events.email import EmailMessagePayload
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.persona.memory_stream import MemoryStreamComponent
from workbench.simulation.run import run_workplace

PLAN_COMPLETION = (
    "[[ ## plan ## ]]\n"
    '{"blocks": [{"start": 32400, "end": 39600, '
    '"focus": "Clear the inbox", "refs": []}, '
    '{"start": 39600, "end": 61200, "focus": "Deep work", "refs": []}]}\n'
    "\n[[ ## completed ## ]]"
)


async def test_day_chain_mints_planning_first() -> None:
    intervals = {f"p{i}": 60 for i in range(4)}
    gm = _gm(_plan(intervals))
    drafts = await gm.consequences(_day_started())
    kinds = [d.tag for d in drafts]
    planning = [d for d in drafts if d.tag == "sim.planning"]
    assert len(planning) == 4
    assert all(int(d.delay) == 9 * 3600 for d in planning)
    first_wake = min(int(d.delay) for d in drafts if d.tag == "sim.wake")
    assert first_wake >= 9 * 3600
    assert kinds.index("sim.planning") < kinds.index("sim.wake"), (
        "planning drafts precede wakes at the same tick"
    )


async def test_plan_event_lands_and_renders(tmp_path: Path) -> None:
    class SwitchLM:
        def __init__(self) -> None:
            self._idle = SequenceLM([DECIDE_IDLE_FALLBACK])
            self._plan = SequenceLM([PLAN_COMPLETION])

        async def complete(self, request):
            prompt = request.messages[-1].content
            if "calendar_today" in prompt:
                return await self._plan.complete(request)
            return await self._idle.complete(request)

    await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=tmp_path / "run",
        inner_lm=SwitchLM(),
        model="test/model",
    )
    events = read_events(tmp_path / "run" / "world.jsonl")
    assert validate_events(events).ok
    plans = [e for e in events if e.tag == "sim.agent.plan"]
    assert plans, "the planning turn grounded a plan event"
    assert plans[0].payload.blocks[0].focus == "Clear the inbox"
    assert plans[0].payload.revision == 1


def _plan_event(entity: str, *, refs: tuple[str, ...] = ()) -> Event:
    payload = SimAgentPlanPayload(
        kind="sim.agent.plan",
        plan_id="pln-000001",
        entity=entity,
        day="2026-03-12",
        revision=1,
        blocks=(PlanBlock(start=32_400, end=61_200, focus="Deep work", refs=refs),),
    )
    return Event(seq=10, time=32_400, tag=payload.kind, source=entity, payload=payload)


def _urgent_email(seq: int, to: str) -> Event:
    payload = EmailMessagePayload(
        kind="email.message",
        message_id=f"msg-{seq:06d}",
        thread_id=f"thr-{seq:06d}",
        in_reply_to=None,
        sender="per-client",
        to=(to,),
        subject="URGENT",
        body="Need this now.",
    )
    return Event(
        seq=seq, time=33_000 + seq, tag=payload.kind, source="x", payload=payload
    )


async def test_replan_trigger_needs_two_urgent_off_plan_arrivals() -> None:
    stream = MemoryStreamComponent(person_id="per-me", entity_name="me")
    await stream.pre_observe(_plan_event("me"))
    assert not stream.replan_pending()

    await stream.pre_observe(_urgent_email(11, "per-me"))
    assert not stream.replan_pending(), "one urgent arrival is not enough"
    await stream.pre_observe(_urgent_email(12, "per-me"))
    assert stream.replan_pending()

    # A fresh plan clears the pressure.
    await stream.pre_observe(_plan_event("me"))
    assert not stream.replan_pending()


async def test_snapshot_rebuild_recomputes_replan_state() -> None:
    stream = MemoryStreamComponent(person_id="per-me", entity_name="me")
    events = [
        _plan_event("me"),
        _urgent_email(11, "per-me"),
        _urgent_email(12, "per-me"),
    ]
    for event in events:
        await stream.pre_observe(event)
    state = stream.get_state()
    fresh = MemoryStreamComponent(person_id="per-me", entity_name="me")
    fresh.set_state(state)
    fresh.rehydrate({str(e.event_id): e for e in events})
    assert fresh.replan_pending() == stream.replan_pending() is True
    assert len(MemoryBullet(text="x", importance=5).refs) == 0
