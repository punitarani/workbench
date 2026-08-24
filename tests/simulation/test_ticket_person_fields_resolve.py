"""A ticket field that holds a person must hold a person's *id*.

The create path resolved `assignee_ref` through the directory; the update
path took whatever the persona typed. So `assignee` was a person id when
a matter was opened and a display name the moment anyone reassigned it,
in a column the served surface types `Ref("person")`.

Measured on a 130-workday world: one matter of 43 carried
`responsible_person = "Cecile Marchand"`. Nothing errored. A join against
the people table simply did not match, and the matter left every result
that grouped by who was responsible — the failure mode is a missing row,
which is the kind a reviewer reads straight past.

The second assertion here is the quieter half of the same bug. The
staleness check compares `change.old` against state holding an id, so a
persona that read the assignee correctly and named them was told its read
was stale. Resolving `old` too is what makes a correct reassignment
possible at all.
"""

import pytest

from core.events import Event
from core.events.control import SimDeliverablePayload
from core.events.people import PersonRecordPayload
from core.events.tickets import FieldChange
from core.intents import TicketCreateSpec, TicketIntent
from simulation.gm.grounded import GroundedGm, IntentRejection, TicketVocabulary

PEOPLE = (
    ("per-ana", "Ana Reyes"),
    ("per-cecile", "Cecile Marchand"),
)


def _gm() -> GroundedGm:
    gm = GroundedGm(
        entity_for_person={person: person.removeprefix("per-") for person, _ in PEOPLE},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open", "Closed"),
            priorities=("Normal",),
            ticket_types=("engagement",),
        ),
    )
    for seq, (person_id, name) in enumerate(PEOPLE, start=1):
        gm.world.apply(
            Event(
                seq=seq,
                event_id=f"evt-{seq:06d}",
                time=0,
                tag="person.record",
                source="gm",
                payload=PersonRecordPayload(
                    kind="person.record",
                    person_id=person_id,
                    name=name,
                    email_address=f"{name.split()[0].lower()}@example.test",
                    title="Associate",
                    department="Litigation",
                    manager=None,
                    affiliation="internal",
                    timezone="UTC",
                ),
            )
        )
    return gm


def _event(seq: int = 100) -> Event:
    return Event(
        seq=seq,
        event_id=f"evt-{seq:06d}",
        time=0,
        tag="sim.deliverable",
        source="gm",
        payload=SimDeliverablePayload(
            kind="sim.deliverable", entity="ana", day="2026-01-05"
        ),
    )


def _open_ticket(gm: GroundedGm) -> str:
    drafts = gm._ground_ticket(
        "ana",
        "per-ana",
        TicketIntent(
            ticket_ref=None,
            create=TicketCreateSpec(
                title="Sandhurst platform acquisition",
                description="Buy-side diligence.",
                requester_ref="Ana Reyes",
                assignee_ref="Ana Reyes",
                status="Open",
                priority="Normal",
                ticket_type="engagement",
            ),
        ),
        _event(),
        0,
    )
    ticket_id = drafts[0].payload.ticket_id
    for offset, draft in enumerate(drafts):
        gm.world.apply(
            Event(
                seq=200 + offset,
                event_id=f"evt-{200 + offset:06d}",
                time=0,
                tag=draft.tag,
                source="gm",
                payload=draft.payload,
            )
        )
    return ticket_id


def _reassign(gm: GroundedGm, ticket_id: str, old: str, new: str):
    return gm._ground_ticket(
        "ana",
        "per-ana",
        TicketIntent(
            ticket_ref=ticket_id,
            changes=(FieldChange(field="assignee", old=old, new=new),),
        ),
        _event(300),
        0,
    )


def test_the_create_path_already_stored_an_id() -> None:
    """The half that was never broken — pinned so a fix to the other half
    cannot quietly change it."""

    gm = _gm()
    ticket_id = _open_ticket(gm)
    assert gm.world.tickets[ticket_id]["assignee"] == "per-ana"


def test_reassigning_by_name_stores_the_id() -> None:
    """The recorded defect, from the direction it arrived."""

    gm = _gm()
    ticket_id = _open_ticket(gm)
    drafts = _reassign(gm, ticket_id, "per-ana", "Cecile Marchand")
    (change,) = drafts[0].payload.changes
    assert change.new == "per-cecile", (
        "a display name in a Ref('person') column joins to nothing"
    )
    assert gm.world.tickets[ticket_id]["assignee"] == "per-cecile"


def test_naming_the_current_assignee_is_not_a_stale_read() -> None:
    """`old` is resolved for the same reason `new` is.

    Unresolved, this comparison is "Ana Reyes" != "per-ana" — a rejection
    telling the persona its correct read of the surface was stale, which
    is how reassignment stayed rare rather than wrong.
    """

    gm = _gm()
    ticket_id = _open_ticket(gm)
    drafts = _reassign(gm, ticket_id, "Ana Reyes", "Cecile Marchand")
    assert drafts, "a correct read of the current assignee was rejected"


def test_a_genuinely_stale_read_is_still_refused() -> None:
    """Resolving `old` must not turn the staleness check off."""

    gm = _gm()
    ticket_id = _open_ticket(gm)
    with pytest.raises(IntentRejection):
        _reassign(gm, ticket_id, "Cecile Marchand", "Ana Reyes")


def test_an_unknown_person_is_refused_rather_than_stored() -> None:
    """A rejection reaches the persona and it names somebody real next
    time. A stored name sits in the column looking like data."""

    gm = _gm()
    ticket_id = _open_ticket(gm)
    with pytest.raises(IntentRejection):
        _reassign(gm, ticket_id, "per-ana", "Someone Not In The Directory")


def test_a_non_person_field_is_left_alone() -> None:
    """`status` is vocabulary, not a directory lookup. Resolving it would
    reject every legal transition."""

    gm = _gm()
    ticket_id = _open_ticket(gm)
    drafts = gm._ground_ticket(
        "ana",
        "per-ana",
        TicketIntent(
            ticket_ref=ticket_id,
            changes=(FieldChange(field="status", old="Open", new="Closed"),),
        ),
        _event(300),
        0,
    )
    (change,) = drafts[0].payload.changes
    assert change.new == "Closed"
