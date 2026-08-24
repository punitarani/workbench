"""A day's plan is clamped to the day, and an empty one is refused.

`_ground_agent_plan` sorts a persona's blocks, clamps each to the end of
the working day, drops any that collapse, and refuses if nothing survives.
Every part of that survived deletion with 640 tests passing.

The clamping is the interesting half. A plan is not a record of what
happened — it is what the persona intends and then works from — so a block
running to 23:00 does not merely look odd in a log: the firm plans a day
it does not have, and every downstream count of when work happens inherits
it. `slack.offhours_share` and `cross.weekend_share_busy` are measured
bands here.

The overlap rule is the other half. Blocks are clamped against the
*previous end*, so two blocks claiming the same hour become one hour of
work rather than two, which is what stops a plan totalling more hours than
a day holds.
"""

from __future__ import annotations

import pytest

from core.events import Event
from core.events.control import SimWakePayload
from core.intents import AgentPlanIntent, PlanBlock
from simulation.chronicle.calendar import CalendarWindow
from simulation.gm.grounded import (
    DayPlan,
    GroundedGm,
    IntentRejection,
    TicketVocabulary,
)

END_OF_DAY = 18 * 3600


def _gm() -> GroundedGm:
    return GroundedGm(
        entity_for_person={"per-ana": "ana"},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
        day_plan=DayPlan(
            window=CalendarWindow(
                start_date="2026-01-05",
                end_date="2026-01-09",
                timezone="America/Los_Angeles",
            ),
            personas=(("ana", 30),),
            end_of_day=END_OF_DAY,
            day_start=9 * 3600,
        ),
    )


def _event() -> Event:
    return Event(
        seq=1,
        event_id="evt-000001",
        time=1,
        tag="sim.wake",
        source="gm",
        caused_by=None,
        payload=SimWakePayload(kind="sim.wake", entity="ana"),
    )


def _plan(*spans: tuple[int, int]) -> AgentPlanIntent:
    return AgentPlanIntent(
        kind="agent_plan",
        day="2026-01-06",
        blocks=tuple(
            PlanBlock(start=start, end=end, focus=f"block {index}", refs=())
            for index, (start, end) in enumerate(spans)
        ),
    )


def _blocks(gm: GroundedGm, intent: AgentPlanIntent):
    (draft,) = gm._ground_agent_plan("ana", intent, _event(), 0)
    return draft.payload.blocks


def test_a_plan_inside_the_day_is_kept_as_written() -> None:
    """Guard the guard: clamping must not be the only thing that ever happens."""

    blocks = _blocks(_gm(), _plan((10 * 3600, 12 * 3600)))
    assert [(b.start, b.end) for b in blocks] == [(10 * 3600, 12 * 3600)]


def test_a_block_running_past_the_end_of_day_is_clamped() -> None:
    blocks = _blocks(_gm(), _plan((16 * 3600, 23 * 3600)))
    assert [(b.start, b.end) for b in blocks] == [(16 * 3600, END_OF_DAY)]


def test_a_plan_wholly_after_the_working_day_is_refused() -> None:
    """Not clamped to nothing and accepted — refused, so the persona replans.

    Silently dropping every block would leave a `sim.agent.plan` naming no
    work, which reads downstream as a person who planned to do nothing.
    """

    with pytest.raises(IntentRejection, match="working day"):
        _gm()._ground_agent_plan("ana", _plan((20 * 3600, 22 * 3600)), _event(), 0)


def test_two_blocks_claiming_one_hour_become_one() -> None:
    """The overlap rule, which is what stops a day totalling more than a day.

    Clamping is against the previous block's end, so the second block
    starts where the first finished rather than where it asked to.
    """

    blocks = _blocks(_gm(), _plan((10 * 3600, 12 * 3600), (10 * 3600, 13 * 3600)))
    spans = [(b.start, b.end) for b in blocks]
    assert spans == [(10 * 3600, 12 * 3600), (12 * 3600, 13 * 3600)]
    assert sum(end - start for start, end in spans) == 3 * 3600


def test_a_block_swallowed_by_an_earlier_one_is_dropped_not_inverted() -> None:
    """A block entirely inside another collapses to nothing and is dropped.

    Without the `end <= start` check it would survive with `end` before
    `start`, and a negative-length block is a duration every consumer of
    this payload would have to defend against.
    """

    blocks = _blocks(_gm(), _plan((10 * 3600, 14 * 3600), (11 * 3600, 12 * 3600)))
    assert [(b.start, b.end) for b in blocks] == [(10 * 3600, 14 * 3600)]
    assert all(b.end > b.start for b in blocks)


def test_blocks_out_of_order_are_sorted_before_they_are_clamped() -> None:
    """The clamp runs against `previous_end`, so order decides the result.

    A persona writes its day in whatever order it thought of things. Take
    the afternoon block first and `previous_end` jumps to the end of it, so
    the morning block starts after lunch or collapses entirely — the plan
    keeps the last thing the persona mentioned and drops the first.

    Every other test in this file hands blocks over already sorted, which
    is why removing the sort left them all green.
    """

    blocks = _blocks(_gm(), _plan((14 * 3600, 16 * 3600), (10 * 3600, 12 * 3600)))
    spans = [(b.start, b.end) for b in blocks]
    assert spans == [(10 * 3600, 12 * 3600), (14 * 3600, 16 * 3600)]
    assert sum(end - start for start, end in spans) == 4 * 3600
