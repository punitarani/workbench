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
