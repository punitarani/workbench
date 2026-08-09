"""Action intents: what an entity wants to do, before the game master grounds it.

Refs are free-form strings (names, ids, titles) resolved by the GM against
world state; unresolvable refs are rejected, never invented.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.events.tickets import FieldChange
from workbench.core.simtime import SimTime


class _Intent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EmailDraft(_Intent):
    to: tuple[str, ...] = Field(
        min_length=1,
        description=(
            "Recipients by full name exactly as they appear in the thread or "
            "directory (e.g. 'Tom Okafor'). Never invent addresses."
        ),
    )
    cc: tuple[str, ...] = Field(
        default=(),
        description="Cc recipients by full name from the thread or directory.",
    )
    subject: str
    body: str
    summary: str


class EmailIntent(_Intent):
    kind: Literal["email"] = "email"
    thread_ref: str | None
    reply_to_ref: str | None
    draft: EmailDraft
    attach_document_refs: tuple[str, ...] = ()


class ChatDraft(_Intent):
    body: str
    summary: str


class ChatIntent(_Intent):
    kind: Literal["chat"] = "chat"
    conversation_ref: str
    reply_to_ref: str | None
    draft: ChatDraft


class TicketCreateSpec(_Intent):
    title: str
    description: str
    requester_ref: str = Field(
        description="Who asked for this, by full name (e.g. 'Jess Alvarez')."
    )
    assignee_ref: str | None = Field(
        description="Who should own it, by full name; null if unassigned."
    )
    status: str = Field(description="One of the workplace's ticket statuses.")
    priority: str = Field(description="One of the workplace's priorities.")
    ticket_type: str = Field(description="One of the workplace's ticket types.")


class TicketIntent(_Intent):
    kind: Literal["ticket"] = "ticket"
    ticket_ref: str | None
    create: TicketCreateSpec | None = None
    changes: tuple[FieldChange, ...] = ()
    comment: str | None = None


class DocumentEdit(_Intent):
    new_content: str
    change_summary: str


class DocumentCreateSpec(_Intent):
    title: str
    path: str
    content: str


class DocumentEditIntent(_Intent):
    kind: Literal["document_edit"] = "document_edit"
    document_ref: str | None
    create: DocumentCreateSpec | None = None
    edit: DocumentEdit | None = None


class CalendarScheduleSpec(_Intent):
    title: str
    start: SimTime
    end: SimTime
    attendee_refs: tuple[str, ...] = Field(min_length=1)
    description: str


class CalendarResponseSpec(_Intent):
    calendar_event_ref: str
    response: Literal["accept", "decline", "tentative"]


class CalendarIntent(_Intent):
    kind: Literal["calendar"] = "calendar"
    schedule: CalendarScheduleSpec | None = None
    respond: CalendarResponseSpec | None = None


class IdleIntent(_Intent):
    kind: Literal["idle"] = "idle"
    until_minutes: int = Field(ge=1)


class FreeformIntent(_Intent):
    """Robustness fallback only; the GM grounds it into a typed intent."""

    kind: Literal["freeform"] = "freeform"
    text: str


ActionIntent = Annotated[
    EmailIntent
    | ChatIntent
    | TicketIntent
    | DocumentEditIntent
    | CalendarIntent
    | IdleIntent
    | FreeformIntent,
    Field(discriminator="kind"),
]
