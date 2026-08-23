"""The loss has to be visible, or the gate that measures it reads zero.

`_ground_timesheet` drops entries logged against engagements this firm
does not have, and when *every* entry is invalid it refuses. The comment
beside that refusal records what it is for:

    Every entry invalid. This used to raise with no note, so the loss was
    invisible: a world whose people had *no* valid code for a whole day
    measured 0.0% dropped and passed the gate that exists to catch exactly
    that. The bias ran one way — the worse the structural gap, the likelier
    a persona has no valid code at all, so the more of the loss
    disappeared.

That is a measurement whose outcome was fixed by construction: the metric
read best precisely when the world was worst. The repair is the two fields
the rejection now carries, `dropped_entries` and `unknown_refs`, and
**neither was tested**. Zeroing `dropped_entries` left 648 tests passing —
which is the original defect, restored, with nothing to notice it.

So these tests are not about the refusal. They are about the number the
refusal carries, because that number is the only thing standing between
this world and a drop rate that reads 0.0% while a sixth of the firm's
time entries vanish.
"""

from __future__ import annotations

import pytest

from core.events import Event
from core.events.control import SimWakePayload
from core.events.people import PersonRecordPayload
from core.intents import TimesheetEntry, TimesheetIntent
from simulation.gm.grounded import GroundedGm, IntentRejection, TicketVocabulary


def _gm() -> GroundedGm:
    gm = GroundedGm(
        entity_for_person={"per-ana": "ana"},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
    )
    gm.world.apply(
        Event(
            seq=1,
            event_id="evt-000001",
            time=1,
            tag="person.record",
            source="gm",
            caused_by=None,
            payload=PersonRecordPayload(
                kind="person.record",
                person_id="per-ana",
                name="Ana Reyes",
                email_address="ana@example.com",
                title="Associate",
                department="Litigation",
                affiliation="internal",
                manager=None,
                timezone="America/Los_Angeles",
            ),
        )
    )
    return gm


def _event() -> Event:
    return Event(
        seq=9,
        event_id="evt-000009",
        time=9,
        tag="sim.wake",
        source="gm",
        caused_by=None,
        payload=SimWakePayload(kind="sim.wake", entity="ana"),
    )


def _sheet(*refs: str) -> TimesheetIntent:
    return TimesheetIntent(
        kind="timesheet",
        entries=tuple(
            TimesheetEntry(
                ticket_ref=ref,
                minutes=30,
                note="reviewed the file",
                billable=True,
            )
            for ref in refs
        ),
    )


def test_every_entry_invalid_is_refused() -> None:
    with pytest.raises(IntentRejection, match="none of these engagements exist"):
        _gm()._ground_timesheet("ana", "per-ana", _sheet("tkt-999999"), _event(), 0)


def test_the_refusal_carries_how_many_were_dropped() -> None:
    """The field that made an invisible loss visible.

    Zeroing it restores the original defect exactly: the world still
    refuses, the persona still loses the day, and the drop rate the gate
    reads is 0.0%.
    """

    with pytest.raises(IntentRejection) as raised:
        _gm()._ground_timesheet(
            "ana", "per-ana", _sheet("tkt-999999", "tkt-999998"), _event(), 0
        )
    assert raised.value.dropped_entries == 2


def test_the_refusal_names_which_engagements_were_unknown() -> None:
    """A count says how much was lost; the refs say what to fix.

    Deduplicated and sorted, so the same bad code twice is one name rather
    than a repeated one, and two runs of the same world produce the same
    note.
    """

    with pytest.raises(IntentRejection) as raised:
        _gm()._ground_timesheet(
            "ana",
            "per-ana",
            _sheet("tkt-999999", "tkt-999998", "tkt-999999"),
            _event(),
            0,
        )
    assert raised.value.unknown_refs == ("tkt-999998", "tkt-999999")
    assert raised.value.dropped_entries == 3


def test_a_dropped_entry_is_counted_even_when_some_are_valid() -> None:
    """The partial case, which does not refuse and must still be recorded.

    A day with one good code and one bad one grounds — silently, if the
    note were dropped — and that is the shape the bias favoured: the
    healthier the persona, the more likely a loss goes unremarked.
    """

    gm = _gm()
    gm.world.tickets["tkt-000001"] = {
        "title": "Coastal Meridian",
        "assignee": "per-ana",
    }
    drafts = gm._ground_timesheet(
        "ana", "per-ana", _sheet("tkt-000001", "tkt-999999"), _event(), 0
    )
    notes = [d for d in drafts if d.payload.kind == "sim.gm.note"]
    assert notes, "a silent drop is the defect this exists to prevent"
    assert "1" in notes[0].payload.note
