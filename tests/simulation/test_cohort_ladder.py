"""R2: wake cohorts on a shared tick grid, seeded phases, quantized
deliveries — the scheduling that lets the windowed engine batch."""

from collections import defaultdict
from pathlib import Path

from mini_workplace import ann_params, make_spec
from test_grounded_gm import last_event, make_gm
from test_grounded_gm import spec as intent_spec
from test_workplace import DECIDE_IDLE_FALLBACK, SequenceLM

from core.actions import IntentAction
from core.events import Event
from core.events.control import SimDayStartedPayload
from core.intents import EmailDraft, EmailIntent
from core.seed import Seed
from simulation.chronicle.calendar import CalendarWindow
from simulation.gm.grounded import DayPlan, GroundedGm, TicketVocabulary
from simulation.gm.timeflow import intent_duration
from simulation.run import run_workplace
from simulation.workplace.spec import PersonSpec

GRID = 30 * 60
DAY_START = 9 * 3600


def _plan(intervals: dict[str, int]) -> DayPlan:
    return DayPlan(
        window=CalendarWindow(
            start_date="2026-03-12", end_date="2026-03-12", timezone="UTC"
        ),
        personas=tuple(intervals.items()),
        end_of_day=17 * 3600 + 1800,
        seed_root=42,
    )


def _gm(plan: DayPlan) -> GroundedGm:
    return GroundedGm(
        entity_for_person={f"per-{name}": name for name in dict(plan.personas)},
        ticket_vocabulary=TicketVocabulary(
            statuses=("open",), priorities=("low",), ticket_types=("general",)
        ),
        day_plan=plan,
    )


def _day_started() -> Event:
    payload = SimDayStartedPayload(kind="sim.day.started", day="2026-03-12")
    return Event(seq=0, time=0, tag=payload.kind, source="gm", payload=payload)


async def test_cohorts_share_grid_ticks() -> None:
    intervals = {f"p{i}": 30 if i % 2 == 0 else 60 for i in range(6)}
    gm = _gm(_plan(intervals))
    drafts = await gm.consequences(_day_started())
    wakes = [d for d in drafts if d.tag == "sim.wake"]
    assert wakes, "the chain mints the day's wakes"

    by_tick: dict[int, set[str]] = defaultdict(set)
    per_entity: dict[str, list[int]] = defaultdict(list)
    for draft in wakes:
        delay = int(draft.delay)
        assert delay >= DAY_START
        assert (delay - DAY_START) % GRID == 0, "every wake lands on a tick"
        by_tick[delay].add(draft.payload.entity)
        per_entity[draft.payload.entity].append(delay)

    assert max(len(entities) for entities in by_tick.values()) >= 3, (
        "shared ticks form real cohorts"
    )
    for entity, times in per_entity.items():
        interval = intervals[entity] * 60
        quantum = max(GRID, -(-interval // GRID) * GRID)
        gaps = {b - a for a, b in zip(times, times[1:], strict=False)}
        assert gaps == {quantum}, f"{entity} wakes every quantized interval"


async def test_phases_are_seeded_and_day_dependent() -> None:
    intervals = {f"p{i}": 60 for i in range(8)}
    gm_one = _gm(_plan(intervals))
    gm_two = _gm(_plan(intervals))
    first = await gm_one.consequences(_day_started())
    second = await gm_two.consequences(_day_started())
    assert first == second, "same seed and day, identical ladder"

    other_payload = SimDayStartedPayload(kind="sim.day.started", day="2026-03-13")
    other_day = Event(
        seq=0, time=0, tag=other_payload.kind, source="gm", payload=other_payload
    )
    gm_three = _gm(
        DayPlan(
            window=CalendarWindow(
                start_date="2026-03-12", end_date="2026-03-13", timezone="UTC"
            ),
            personas=tuple(intervals.items()),
            end_of_day=17 * 3600 + 1800,
            seed_root=42,
        )
    )
    third = await gm_three.consequences(other_day)
    first_wakes = {
        (d.payload.entity, int(d.delay)) for d in first if d.tag == "sim.wake"
    }
    third_wakes = {
        (d.payload.entity, int(d.delay)) for d in third if d.tag == "sim.wake"
    }
    assert first_wakes != third_wakes, "phases reshuffle day to day"


async def test_grounded_deliveries_are_quantized() -> None:
    gm = make_gm()
    gm._delivery_quantum = 300
    intent = EmailIntent(
        thread_ref=None,
        reply_to_ref=None,
        draft=EmailDraft(
            to=("Jess Alvarez",),
            subject="Quantized",
            body="A body long enough to cross one minute of drafting time.",
            summary="s",
        ),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), intent_spec(), last_event()
    )
    email_drafts = [d for d in decision.drafts if d.tag == "email.message"]
    assert email_drafts, decision.drafts
    delay = int(email_drafts[0].delay)
    assert delay % 300 == 0
    assert delay >= intent_duration(intent)


async def test_windowed_mini_run_forms_batches(tmp_path: Path) -> None:
    extra_people = tuple(
        PersonSpec(
            person_id=f"per-x{i}",
            name=f"Xan Doe{i}",
            email_address=f"x{i}@mini.example",
            title="Counsel",
            department="Legal",
            manager=None,
            affiliation="internal",
            persona=ann_params().model_copy(
                update={"person_id": f"per-x{i}", "name": f"Xan Doe{i}"}
            ),
        )
        for i in range(4)
    )
    spec = make_spec()
    spec = spec.model_copy(update={"people": (*spec.people, *extra_people)})

    batches: list[int] = []
    import simulation.run as run_module

    original_run = run_module.InterruptEngine.run

    async def probed(self, stop, *, on_step=None, on_batch=None, window=1):
        return await original_run(
            self,
            stop,
            on_step=on_step,
            on_batch=lambda results: batches.append(len(results)),
            window=window,
        )

    run_module.InterruptEngine.run = probed
    try:
        await run_workplace(
            spec,
            seed=Seed(root=42),
            out_dir=tmp_path / "run",
            inner_lm=SequenceLM([DECIDE_IDLE_FALLBACK]),
            model="test/model",
            window=8,
        )
    finally:
        run_module.InterruptEngine.run = original_run
    assert max(batches) >= 3, f"cohort wakes batch under windowing: {batches}"
