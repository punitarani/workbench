from typing import Literal

from pydantic import Field

from core.events._base import Payload
from core.ids import OrgId, PersonId, TicketId


class TicketField(Payload):
    name: str
    value: str


class FieldChange(Payload):
    field: str
    old: str | None
    new: str | None


# The mutable fields of a ticket, in the order the record folds them.
FOLDED_TICKET_FIELDS = ("title", "description", "assignee", "status", "priority")

# Which of those hold a person rather than free text. A column typed
# `Ref("person")` that holds a display name joins to nothing, and the row
# leaves every grouped result without erroring anywhere.
PERSON_TICKET_FIELDS = frozenset({"assignee"})


def collapse_field_changes(
    changes: "tuple[FieldChange, ...]",
) -> "tuple[FieldChange, ...]":
    """Two changes to one field in a single update are one change.

    A recorded law firm produced this, once in 377 updates:

        status: 'Intake' -> 'Awaiting Court'
        status: 'Intake' -> 'Active'

    in a single event. Both claim the same prior value, and only the
    first is right; state ends at `Active` and every later event chains
    from `Active`, so nothing downstream is ambiguous about what the
    matter's status *is*.

    What is wrong is the history. `matter_history` gained a row saying
    the matter moved to `Awaiting Court`, a transition that never
    durably happened — and a status task reads exactly that table. The
    net change is what took place: the value it started from, the value
    it ended at, one row.

    Collapsing rather than rejecting is deliberate. The author did mean
    to move the status; they said so twice and disagreed with
    themselves. Discarding the whole update would throw away the other
    fields in it too.
    """

    first_old: dict[str, str | None] = {}
    last_new: dict[str, str | None] = {}
    order: list[str] = []
    for change in changes:
        if change.field not in first_old:
            order.append(change.field)
            first_old[change.field] = change.old
        last_new[change.field] = change.new
    return tuple(
        FieldChange(field=field, old=first_old[field], new=last_new[field])
        for field in order
    )


class TicketCreatedPayload(Payload):
    kind: Literal["ticket.created"]
    ticket_id: TicketId
    actor: PersonId
    title: str
    description: str
    requester: PersonId
    assignee: PersonId | None
    # Status/priority/type vocabularies are workplace-declared; the GM enforces
    # them at resolution time. Core stays domain-neutral.
    status: str
    priority: str
    ticket_type: str
    client_ref: OrgId | None = None
    # An institution-wide code anybody may book to — administration,
    # internal meetings, business development. Declared, never inferred.
    #
    # It was inferred, from `client_ref is None`, and that is also the
    # default for every ticket a persona opens at runtime: the grounding
    # path does not set a client. So real matters people created were
    # classified as standing codes, hoisted to the head of every bookable
    # list, and — because the snapshot drops client-less tickets from
    # tracker and effort rows — the time booked to them left the client
    # record silently. Measured on a live world at day nine: two runtime
    # tickets, 97 of 1,323 entries, 3,038 minutes.
    #
    # Defaulting False means a lookup miss errs toward "not standing",
    # which is the safe direction: the cost is a code that gets bounded
    # away, not work that disappears.
    standing: bool = False
    fields: tuple[TicketField, ...] = ()


class TicketUpdatedPayload(Payload):
    kind: Literal["ticket.updated"]
    ticket_id: TicketId
    actor: PersonId
    changes: tuple[FieldChange, ...] = Field(min_length=1)


class TicketCommentedPayload(Payload):
    kind: Literal["ticket.commented"]
    ticket_id: TicketId
    actor: PersonId
    body: str
