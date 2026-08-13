from typing import Literal

from pydantic import Field

from workbench.core.events._base import Payload
from workbench.core.ids import OrgId, PersonId, TicketId


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
