"""Action intents: what an entity wants to do, before the game master grounds it.

Refs are free-form strings (names, ids, titles) resolved by the GM against
world state; unresolvable refs are rejected, never invented.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.events.agent import MemoryBullet, PlanBlock
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
        description=(
            "The person who asked for this, by their full name as listed in "
            "the situation. A person, never a company."
        )
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


class ReactionIntent(_Intent):
    kind: Literal["reaction"] = "reaction"
    chat_message_ref: str
    emoji: str


class TimeLogIntent(_Intent):
    """Record time against a ticket. The rate comes from the persona's
    profile at grounding time, never from the model."""

    kind: Literal["time_log"] = "time_log"
    ticket_ref: str
    minutes: int = Field(ge=1)
    note: str
    billable: bool = True


class IdleIntent(_Intent):
    kind: Literal["idle"] = "idle"
    until_minutes: int = Field(ge=1)


class FreeformIntent(_Intent):
    """Robustness fallback only; the GM grounds it into a typed intent."""

    kind: Literal["freeform"] = "freeform"
    text: str


class AgentNoteIntent(_Intent):
    """Persist a reflection or summary as a sim.agent.memory event. The
    GM drops unknown refs rather than rejecting: cognition must not fail
    a day over a mistyped id."""

    kind: Literal["agent_note"] = "agent_note"
    note_kind: Literal["daily_summary", "weekly_summary", "note"] = "note"
    day: str
    bullets: tuple[MemoryBullet, ...] = Field(min_length=1)
    open_loops: tuple[str, ...] = ()


class AgentPlanIntent(_Intent):
    """Persist a day plan as a sim.agent.plan event; the GM clamps blocks
    to the working day instead of rejecting."""

    kind: Literal["agent_plan"] = "agent_plan"
    day: str
    blocks: tuple[PlanBlock, ...] = Field(min_length=1)


ActionIntent = Annotated[
    EmailIntent
    | ChatIntent
    | TicketIntent
    | DocumentEditIntent
    | CalendarIntent
    | ReactionIntent
    | TimeLogIntent
    | IdleIntent
    | FreeformIntent
    | AgentNoteIntent
    | AgentPlanIntent,
    Field(discriminator="kind"),
]
