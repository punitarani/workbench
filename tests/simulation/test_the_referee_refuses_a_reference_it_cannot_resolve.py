"""References and vocabulary the referee will not invent for a persona.

Four refusals, all of which survived deletion with 635 tests passing:

    unknown ticket status on create   the vocabulary is the workplace's
    unknown ticket on update          an engagement this firm never opened
    unknown document on edit          a file the room does not hold
    a plan wholly outside the day     a day of work scheduled at 3am

They share a shape and a consequence. None crashes: the referee would go
on and mint a payload naming something that does not exist, the projection
would serve it, and `analysis.coherence` would report it as dangling at
materialize time — hours later, as a build failure, with no way back to
the persona who could have fixed it. A rejection is the only feedback loop
this firm has, and its own comment says so: *"the rejection is feedback the
persona remembers."*

The vocabulary case is the odd one and the reason to test it separately: a
status is not dangling, it is simply not a word this workplace uses. Left
unrefused it does not break a reference, it quietly widens the workplace's
own vocabulary from inside — and `clio`'s status column becomes whatever
the personas felt like typing.
"""

from __future__ import annotations

import pytest

from core.events import Event
from core.events.control import SimWakePayload
from core.events.people import PersonRecordPayload
from core.intents import (
    DocumentEdit,
    DocumentEditIntent,
    TicketCreateSpec,
    TicketIntent,
)
from simulation.gm.grounded import GroundedGm, IntentRejection, TicketVocabulary


def _gm() -> GroundedGm:
    """A referee with one person on the record.

    Without the `person.record` the requester does not resolve and every
    ticket test dies on `unknown person` -- which is the *other* guard in
    this file firing on the fixture, and a reminder that a world is what
    has been applied to it rather than what the constructor was told.
    """

    gm = GroundedGm(
        entity_for_person={"per-ana": "ana"},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open", "Closed"),
            priorities=("Normal", "High"),
            ticket_types=("engagement",),
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
        seq=999,
        event_id="evt-000999",
        time=999,
        tag="sim.wake",
        source="gm",
        caused_by=None,
        payload=SimWakePayload(kind="sim.wake", entity="ana"),
    )


def _create(status: str = "Open") -> TicketIntent:
    return TicketIntent(
        kind="ticket",
        ticket_ref=None,
        create=TicketCreateSpec(
            title="Coastal Meridian — regulatory inquiry",
            description="respond to the examiner's letter",
            requester_ref="Ana Reyes",
            assignee_ref=None,
            status=status,
            priority="Normal",
            ticket_type="engagement",
        ),
        changes=(),
        comment=None,
    )


def test_a_ticket_in_the_workplace_vocabulary_is_created() -> None:
    """Guard the guard: if no ticket can be created, the refusals prove nothing."""

    assert _gm()._ground_ticket("ana", "per-ana", _create(), _event(), 0)


def test_a_status_this_workplace_does_not_use_is_refused() -> None:
    """Not a dangling reference — a word the firm does not say.

    Unrefused, this widens the workplace's own vocabulary from inside, and
    clio's status column becomes whatever the personas felt like typing.
    """

    with pytest.raises(IntentRejection, match="unknown ticket status"):
        _gm()._ground_ticket("ana", "per-ana", _create("Percolating"), _event(), 0)


def test_updating_a_ticket_this_firm_never_opened_is_refused() -> None:
    intent = TicketIntent(
        kind="ticket",
        ticket_ref="tkt-999999",
        create=None,
        changes=(),
        comment="bumping this",
    )
    with pytest.raises(IntentRejection, match="unknown ticket"):
        _gm()._ground_ticket("ana", "per-ana", intent, _event(), 0)


def test_editing_a_document_the_file_room_does_not_hold_is_refused() -> None:
    """Coherence catches the dangling row later; the persona cannot.

    "revises doc-999999, which no document is" fails a build hours after
    the turn that caused it, and by then there is nobody to tell.
    """

    intent = DocumentEditIntent(
        kind="document_edit",
        document_ref="doc-999999",
        create=None,
        edit=DocumentEdit(
            new_content="A further paragraph.",
            change_summary="expanded the analysis",
        ),
    )
    with pytest.raises(IntentRejection, match="unknown document"):
        _gm()._ground_document("ana", "per-ana", intent, _event(), 0)


def test_naming_someone_this_firm_has_never_heard_of_is_refused() -> None:
    """The guard that fired on this file's own fixture.

    `_resolve_people` refuses a name the directory does not hold rather
    than minting one, which is what keeps a ticket's requester a person
    with a record. Mutating it away left the four tests above green,
    because every one of them names somebody real -- the same reason every
    other refusal in this sweep was untested.
    """

    intent = _create().model_copy(
        update={
            "create": _create().create.model_copy(
                update={"requester_ref": "Someone Who Does Not Work Here"}
            )
        }
    )
    with pytest.raises(IntentRejection, match="unknown person"):
        _gm()._ground_ticket("ana", "per-ana", intent, _event(), 0)


def test_answering_an_invitation_this_world_never_issued_is_refused() -> None:
    """The guard whose comment records the incident that produced it.

    *"Every other surface rejects an id it has never issued; without this
    one, an invented cal- ref became a response event and the materializer
    refused the whole log as incoherent."*

    A guard added after a whole recording was thrown away, and nothing
    exercised it. The cost of losing it again is not one bad row: a
    response naming no event fails materialization, so the log is
    unusable and the hours that produced it are gone.
    """

    from core.intents import CalendarIntent, CalendarResponseSpec

    intent = CalendarIntent(
        kind="calendar",
        schedule=None,
        respond=CalendarResponseSpec(
            calendar_event_ref="cal-999999", response="accept"
        ),
    )
    with pytest.raises(IntentRejection, match="unknown calendar event"):
        _gm()._ground_calendar("ana", "per-ana", intent, _event(), 0)


def test_a_ticket_update_that_changes_nothing_is_refused() -> None:
    """An update carrying no change and no note is a turn that says nothing.

    It grounds to no drafts, so without the guard the persona's turn
    produces an empty tuple: no event, no feedback, and a wake spent. The
    refusal is what tells them to say what moved or why nothing did.
    """

    gm = _gm()
    # A ticket that exists, so this reaches the no-op guard rather than the
    # earlier "needs a ticket_ref or create spec". The first version of
    # this test passed against that one instead -- a rejection for the
    # wrong reason reads exactly like a rejection for the right one, and
    # only mutating the intended guard away showed the difference.
    (draft,) = gm._ground_ticket("ana", "per-ana", _create(), _event(), 0)
    gm.world.apply(
        Event(
            seq=2,
            event_id="evt-000002",
            time=2,
            tag=draft.payload.kind,
            source="gm",
            caused_by=None,
            payload=draft.payload,
        )
    )
    empty = TicketIntent(
        kind="ticket",
        ticket_ref=draft.payload.ticket_id,
        create=None,
        changes=(),
        comment=None,
    )
    with pytest.raises(IntentRejection, match="changes nothing"):
        gm._ground_ticket("ana", "per-ana", empty, _event(), 0)
