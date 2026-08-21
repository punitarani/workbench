"""An invitation nobody is shown is an invitation nobody answers.

`respond_invite` is in the persona's verb list, `CalendarResponseSpec` is
a schema, and the referee grounds it into a `calendar.response` event.
Every piece was correct. Nothing put an unanswered invitation in front of
the person it was sent to, so the only replies in a whole recording came
from personas who happened to retrieve the meeting from memory for some
other reason.

Measured on a corrected-engine pilot before this fix: **187 responses to
2,765 invitations — 93% unanswered, and one decline in the entire
record.** A diary in which nobody ever says no cannot be asked who was
free, who double-booked, or what got moved.

This is the fourth instance of the same defect in this world
(see the pending *chat* item, which named the conversation instead of the
message and produced 3 replies in 3,177 messages). The shape is always:
a capability that works, and no caller — and the surface it should fill
is empty rather than wrong, so no integrity check can see it.
"""

from persona_fixtures import observed_events

from core.events import Event
from core.events.calendar import (
    CalendarEventScheduledPayload,
    CalendarResponsePayload,
)
from simulation.persona.working_memory import WorkingMemoryComponent

ME = "per-daniel-reyes"
ORGANIZER = "per-jess-alvarez"


def _invitation(
    event_id: str, seq: int, *, at: int, start: int, organizer: str = ORGANIZER
) -> Event:
    return Event(
        seq=seq,
        time=at,
        tag="calendar.event.scheduled",
        source="x",
        payload=CalendarEventScheduledPayload(
            kind="calendar.event.scheduled",
            calendar_event_id=event_id,
            organizer=organizer,
            title=f"Vantage redline walkthrough {event_id[-1]}",
            start=start,
            end=start + 3600,
            attendees=(ME, ORGANIZER),
            description="Walk the redlines together.",
        ),
    )


def _ordered(extra: list[Event]) -> list[Event]:
    """Time order, because a real stream is in time order.

    `last_time()` reads the *last* event rather than the maximum, which is
    right for a stream and wrong for a fixture that appends a past event
    at the end — the clock would jump backwards and a meeting that has
    already happened would still look like it was in the future.
    """

    return sorted([*observed_events(), *extra], key=lambda e: (int(e.time), e.seq))


async def _memory(extra: list[Event]) -> WorkingMemoryComponent:
    memory = WorkingMemoryComponent(person_id=ME)
    for event in _ordered(extra):
        await memory.pre_observe(event)
    return memory


async def test_an_unanswered_invitation_is_pending() -> None:
    memory = await _memory([_invitation("cal-000001", 90, at=36000, start=200_000)])
    items = {item.ref: item for item in memory.pending_items()}
    assert "cal-000001" in items, (
        f"an invitation to a future meeting is not pending: {sorted(items)}"
    )
    assert items["cal-000001"].channel == "invitation"
    assert "Vantage" in items["cal-000001"].summary


async def test_answering_it_clears_it() -> None:
    events = [
        _invitation("cal-000001", 90, at=36000, start=200_000),
        Event(
            seq=91,
            time=37000,
            tag="calendar.response",
            source="x",
            payload=CalendarResponsePayload(
                kind="calendar.response",
                calendar_event_id="cal-000001",
                responder=ME,
                response="accept",
            ),
        ),
    ]
    memory = await _memory(events)
    assert "cal-000001" not in {item.ref for item in memory.pending_items()}


async def test_my_own_meeting_is_not_an_invitation_to_myself() -> None:
    memory = await _memory(
        [_invitation("cal-000002", 90, at=36000, start=200_000, organizer=ME)]
    )
    assert "cal-000002" not in {item.ref for item in memory.pending_items()}


async def test_a_meeting_already_under_way_is_not_outstanding() -> None:
    """Otherwise every past invitation crowds the list forever.

    The fixture's clock sits at 35000; a meeting that started at 20000 is
    not work the person still owes anyone an answer about.
    """

    memory = await _memory([_invitation("cal-000003", 90, at=10000, start=20000)])
    assert "cal-000003" not in {item.ref for item in memory.pending_items()}


async def test_pending_invitations_survive_a_resume() -> None:
    events = [_invitation("cal-000001", 90, at=36000, start=200_000)]
    memory = await _memory(events)
    fresh = WorkingMemoryComponent(person_id=ME)
    fresh.set_state(memory.get_state())
    fresh.rehydrate({str(e.event_id): e for e in _ordered(events)})
    assert fresh.pending_items() == memory.pending_items()
