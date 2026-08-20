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
